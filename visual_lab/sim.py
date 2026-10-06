"""Isaac adapter. All heavy imports happen after the single SimulationApp starts.

Uses the LOCAL NVIDIA tutorial for scene/robot/controller helpers. The sequencing,
frame accounting, timeouts, camera and evaluator are this kit's own code.
"""
from __future__ import annotations
import math
from pathlib import Path
from .core import LabError, PHASES, phase_result, vector3
from .upstream import load_tutorial
from .capture import SceneCamera


class IsaacScene:
    def __init__(self, app, config: dict, tutorial_path: Path, *, xrdf_dir=None,
                 urdf="robot.urdf", xrdf="robot.xrdf", sim_device="cuda",
                 record_every=0, record_directory: Path | None = None):
        import numpy as np
        import carb
        import omni.timeline
        from isaacsim.core.simulation_manager import SimulationManager
        from isaacsim.core.experimental.prims import GeomPrim
        self.np = np
        self.app = app
        self.c = config
        self.manager = SimulationManager
        self.timeline = omni.timeline.get_timeline_interface()
        self.camera = None
        self.frames = 0
        self.record_every = record_every
        self.record_directory = record_directory
        self.recorded_frames = 0
        self.gripper_command = 0.0
        self.scenario = None
        SimulationManager.setup_simulation(dt=config["physics_dt"], device=sim_device)
        self.physics_pose_sync = self._configure_pose_updates(carb.settings.get_settings())
        cls, self.source_metadata = load_tutorial(tutorial_path)
        expected = {"_ROBOT_PRIM_PATH": "/World/ur10e_robot", "_CUBE_PRIM_PATH": "/World/cube",
                    "_EE_LINK_NAME": "right_inner_finger", "_GRIPPER_JOINT": "finger_joint",
                    "_OPEN_POS": 0.0, "_CLOSED_POS": 0.5}
        for name, value in expected.items():
            if getattr(cls, name, None) != value:
                raise LabError(f"Installed tutorial differs at {name}: expected {value!r}. Update the adapter explicitly.")
        self.scenario = cls(xrdf_dir=xrdf_dir, urdf_filename=urdf, xrdf_filename=xrdf,
            cube_position=np.array(config["cube_position_m"], dtype=float),
            target_position=np.array(config["target_position_m"], dtype=float))
        # Trusted installed setup_scene; no second SimulationApp and no upstream main loop.
        app.run_coroutine(self.scenario.setup_scene())
        app.update()
        self._decorate_scene()
        self.camera = SceneCamera(config["camera"])
        self.timeline.play()
        app.update()
        self.scenario.initialize_after_play()
        if self.scenario._finger_idx is None or self.scenario._ee_prim is None:
            raise LabError("UR10e link/joint lookup failed. This adapter supports the packaged tutorial asset only.")
        self.cube_prim = GeomPrim(paths=self.scenario._CUBE_PRIM_PATH)
        self.gripper_command = float(self.scenario._OPEN_POS)
        dofs = len(self.scenario._articulation.dof_names)
        for _ in range(config["warmup_frames"]):
            self.scenario._articulation.set_dof_position_targets([0.0] * dofs)
            self._physics_step(record=False)
        self.timeline.pause()

    def _configure_pose_updates(self, settings):
        """Keep default USD pose readers and rendering in sync with physics.

        CUDA setup enables Fabric and suppresses USD readback. Our GeomPrim
        readers use USD, so restore USD updates before loading/playing the scene.
        This trades some readback overhead for one consistent state source; it
        does not change the requested physics device or advance the simulation.
        """
        self.manager.enable_fabric(False)
        settings.set_bool("/physics/suppressReadback", False)
        state = {"pose_backend": "usd", "fabric_enabled": self.manager.is_fabric_enabled(),
                 "update_to_usd": settings.get_as_bool("/physics/updateToUsd"),
                 "suppress_readback": settings.get_as_bool("/physics/suppressReadback")}
        if state["fabric_enabled"] or not state["update_to_usd"] or state["suppress_readback"]:
            raise LabError(f"Cannot synchronize physics poses to USD: {state}")
        return state

    def _decorate_scene(self):
        """Make the visual task defined: red object, blue goal visible in rendered RGB.

        Blue strips have no collision/rigid-body API and do not change the ground.
        The same decorations are used in baseline, shadow and visual modes.
        """
        import omni.usd
        from pxr import UsdGeom, Gf
        stage = omni.usd.get_context().get_stage()
        cube = stage.GetPrimAtPath(self.scenario._CUBE_PRIM_PATH)
        if not cube.IsValid():
            raise LabError("Tutorial cube was not created")
        UsdGeom.Gprim(cube).GetDisplayColorAttr().Set([Gf.Vec3f(0.85, 0.04, 0.04)])
        tx, ty, _ = self.c["target_position_m"]
        # 12 cm outline; score still uses center <= 5 cm, not the outline geometry.
        half, width, height = 0.06, 0.004, 0.001
        strips = [([tx-half,ty,height/2],[width,2*half,height]),
                  ([tx+half,ty,height/2],[width,2*half,height]),
                  ([tx,ty-half,height/2],[2*half,width,height]),
                  ([tx,ty+half,height/2],[2*half,width,height])]
        for i, (pos, scale) in enumerate(strips):
            geom = UsdGeom.Cube.Define(stage, f"/World/VisualGoal/edge_{i}")
            geom.CreateSizeAttr(1.0)
            geom.CreateDisplayColorAttr([Gf.Vec3f(0.02, 0.18, 0.95)])
            transform = UsdGeom.Xformable(geom.GetPrim())
            transform.AddTranslateOp().Set(Gf.Vec3d(*pos))
            transform.AddScaleOp().Set(Gf.Vec3f(*scale))

    def _physics_step(self, *, record=True):
        if not self.app.is_running():
            raise LabError("SimulationApp window was closed")
        # Kit applies queued play/pause requests at the next update. Check the
        # committed state after this same counted step, not immediately after play().
        self.app.update()
        if not self.timeline.is_playing():
            raise LabError("Timeline paused during an execution segment")
        if not self.manager.is_simulating():
            raise LabError("Physics is not simulating; verify the installed Tutorial 9 first")
        self.frames += 1
        if record and self.record_every and self.frames % self.record_every == 0:
            png = self.capture()
            path = self.record_directory / f"frame_{self.recorded_frames:06d}.png"
            path.write_bytes(png)
            self.recorded_frames += 1
            self.timeline.play()

    def proprioception(self) -> dict:
        s = self.scenario
        ee = s._ee_prim.get_world_poses()[0].numpy()[0].tolist()
        positions = s._articulation.get_dof_positions().numpy().reshape(-1)
        return {"ee_world_position_m": vector3(ee, "ee_position"),
                "finger_joint_position_rad": float(positions[s._finger_idx])}

    def private_truth(self) -> dict:
        # DO NOT insert this into model_state. It is evaluator/debugger-only information.
        cube = self.cube_prim.get_world_poses()[0].numpy()[0].tolist()
        return {"cube_world_position_m": vector3(cube, "cube_position"),
                "target_world_position_m": list(self.c["target_position_m"]),
                "sim_time_seconds": float(self.timeline.get_current_time()), "physics_updates": self.frames}

    def capture(self) -> bytes:
        self.timeline.pause()
        before_q = self.scenario._articulation.get_dof_positions().numpy().copy()
        before_cube = self.cube_prim.get_world_poses()[0].numpy().copy()
        image = self.camera.png()
        after_q = self.scenario._articulation.get_dof_positions().numpy()
        after_cube = self.cube_prim.get_world_poses()[0].numpy()
        if not self.np.allclose(before_q, after_q, rtol=0, atol=1e-6) or not self.np.allclose(before_cube, after_cube, rtol=0, atol=1e-6):
            raise LabError("Capture advanced physics: image/state pair would be inconsistent")
        return image

    def _sync_world(self):
        s = self.scenario
        s._world_binding.get_world_interface().update_world_to_robot_root_transforms(s._articulation.get_world_poses())
        s._world_binding.synchronize_transforms()

    def _controller_tool_world_position(self):
        """Evaluate the controller's tool FK from measured, not commanded, joints.

        This is a position in the controller model, not a measured grasp center
        or proof that the URDF matches the physical asset. Finger telemetry and
        final physical cube scoring remain separate.
        """
        import cumotion
        s = self.scenario
        robot = s._cumotion_robot
        names = s._articulation.dof_names
        if any(name not in names for name in robot.controlled_joint_names):
            raise LabError("Controller FK controlled joint is missing from the articulation")
        measured = s._articulation.get_dof_positions().numpy().reshape(-1).tolist()
        q = self.np.array([measured[names.index(name)] for name in robot.controlled_joint_names], dtype=float).reshape(-1, 1)
        local = vector3(robot.kinematics.position(q, s._tool_frame).reshape(-1).tolist(), "controller_tool_position")
        positions, orientations = s._articulation.get_world_poses()
        origin = vector3(positions.numpy().reshape(-1).tolist(), "robot_base_position")
        quaternion = orientations.numpy().reshape(-1).tolist()  # Isaac and Rotation3 use wxyz.
        if len(quaternion) != 4 or not all(math.isfinite(v) for v in quaternion):
            raise LabError("Invalid robot base quaternion for controller FK")
        rotation = cumotion.Rotation3(*quaternion).matrix().tolist()
        return vector3([origin[i] + sum(rotation[i][j]*local[j] for j in range(3)) for i in range(3)],
                       "controller_tool_world_position")

    def _write_joint_targets(self, positions, dof_indices=None):
        """Merge the arm and finger command before one articulation target write.

        The tensor subset setter reads and rewrites the full target vector. Two
        setters in one frame can lose an earlier pending arm command if the read
        exposes committed rather than pending targets.
        """
        def flat(data):
            if hasattr(data, "numpy"):
                data = data.numpy()
            if hasattr(data, "reshape"):
                data = data.reshape(-1)
            if hasattr(data, "tolist"):
                data = data.tolist()
            return list(data)

        s = self.scenario
        dofs = len(s._articulation.dof_names)
        values = flat(positions)
        indices = list(range(dofs)) if dof_indices is None else flat(dof_indices)
        if not values or len(values) != len(indices):
            raise LabError("Joint target values must be nonempty and match their indices")
        if any(isinstance(i, bool) or not isinstance(i, int) or not 0 <= i < dofs for i in indices):
            raise LabError("Joint target index is invalid for this articulation")
        if len(set(indices)) != len(indices):
            raise LabError("Joint target indices contain duplicates")
        if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) for v in values):
            raise LabError("Joint target values must be finite numbers")
        finger = s._finger_idx
        if not isinstance(finger, int) or not 0 <= finger < dofs:
            raise LabError("Gripper joint index is invalid")
        if not math.isfinite(self.gripper_command):
            raise LabError("Gripper command must be finite")
        merged = dict(zip(indices, values))
        merged[finger] = self.gripper_command
        s._articulation.set_dof_position_targets(
            positions=list(merged.values()), dof_indices=list(merged))
        return {"dof_indices": list(merged), "positions_rad": list(merged.values())}

    def execute(self, action: str) -> dict:
        if action not in PHASES:
            raise LabError(f"Cannot execute {action}")
        s = self.scenario
        # Select a tutorial target, NOT a tutorial next-state transition.
        s._event = PHASES.index(action)
        target = s._phase_ee_target()
        xyz = vector3(target.tolist(), "skill_target")
        if abs(xyz[0]) > 1.5 or abs(xyz[1]) > 1.5 or not 0.02 <= xyz[2] <= 1.5:
            raise LabError(f"Configured skill target outside the demo guard box: {xyz}")
        is_gripper = action in {"grasp", "release"}
        held_joints = s._articulation.get_dof_positions().numpy().reshape(-1).tolist()
        start_ee = self.proprioception()["ee_world_position_m"]
        if is_gripper:
            self.gripper_command = float(s._CLOSED_POS if action == "grasp" else s._OPEN_POS)
        else:
            self._sync_world()
            # Every selected motion may follow any other phase; always reset here.
            if not s._controller.reset(s._estimated_state(), s._make_setpoint(target), t=0.0):
                raise LabError(f"RMPflow reset failed for {action}")
        maximum = self.c["tutorial_phase_limits"][s._event] * self.c["frame_scale"]
        self.timeline.play()
        status = None
        ee_error = gripper_error = 0.0
        controller_command_frames = 0
        for frame in range(1, maximum + 1):
            if is_gripper:
                # Hold the arm, but not the gripper DOF, while opening/closing.
                last_joint_command = self._write_joint_targets(held_joints)
            else:
                self._sync_world()
                desired = s._controller.forward(s._estimated_state(), s._make_setpoint(target), (frame-1)*self.c["physics_dt"])
                if desired is None or desired.joints is None or desired.joints.positions is None:
                    raise LabError(f"RMPflow returned no joint position command for {action} at frame {frame}")
                last_joint_command = self._write_joint_targets(desired.joints.positions, desired.joints.position_indices)
                controller_command_frames += 1
            self._physics_step()
            observed = self.proprioception()
            ee_error = math.dist(observed["ee_world_position_m"], xyz)
            tool_position = self._controller_tool_world_position()
            tool_error = math.dist(tool_position, xyz)
            gripper_error = abs(observed["finger_joint_position_rad"] - self.gripper_command)
            status = phase_result(action, frame, tool_error, gripper_error, self.c)
            if status:
                break
        self.timeline.pause()
        final_joints = s._articulation.get_dof_positions().numpy().reshape(-1).tolist()
        return {"action": action, "status": status, "frames": frame,
                "target_world_position_m": xyz, "ee_error_m": ee_error,
                "convergence_position_source": "controller_model_fk_from_measured_joints",
                "controller_tool_frame": s._tool_frame,
                "controller_tool_world_position_m": tool_position, "controller_tool_error_m": tool_error,
                "gripper_target_rad": self.gripper_command, "gripper_error_rad": gripper_error,
                "controller_command_frames": controller_command_frames,
                "last_joint_command": last_joint_command,
                "ee_world_position_start_m": start_ee,
                "ee_world_position_end_m": observed["ee_world_position_m"],
                "joint_positions_start_rad": held_joints, "joint_positions_end_rad": final_joints,
                "max_joint_displacement_rad": max((abs(a-b) for a, b in zip(held_joints, final_joints)), default=0.0)}

    def settle(self):
        """Both baseline and model get the same fixed post-retract settling interval."""
        self.timeline.play()
        for _ in range(self.c["settle_frames"]):
            self.scenario._set_gripper(self.gripper_command)
            self._physics_step()
        self.timeline.pause()

    def close(self):
        self.timeline.pause()
        if self.camera is not None:
            self.camera.close()
