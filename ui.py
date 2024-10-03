import time
import concurrent.futures

import bpy

from . import core
from . import settings


class TEXCOMPACTOR_PT_main_panel(bpy.types.Panel):
    bl_label = "Texture Compactor"
    bl_idname = "TEXCOMPACTOR_PT_main_panel"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "render"

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        layout.use_property_decorate = False
        scene = context.scene

        # show the rest of the UI after scanning is done
        before, after, delta, num_of_changes = core.tally_sizes(context.scene.TC_texture_metadata)
        is_optimized = core.is_optimized(context.scene.TC_texture_metadata)

        # always show unless texture is already optimized

        col = layout.column()
        col.operator("texture_compactor.scan_textures", icon="FILE_REFRESH")

        # bail early if scanning isn't done
        if not context.scene.TC_texture_metadata:
            return

        # UI after optimizing
        if is_optimized:
            row = layout.row()
            col = row.split(factor=0.9)
            factor = 1
            if context.scene.TC_texture_swap == "0":
                text = f"Texture Memory: {int(before)}MB"
            else:
                text = f"Texture Memory: {int(after)}MB"

            col.progress(factor=factor, text=text)
            col.operator("texture_compactor.show_report", text="", icon="FILE")

            row = layout.row()
            row.prop(scene, "TC_texture_swap", expand=True)
            row = layout.row()
        else:
            row = layout.row()
            row.prop(scene, "TC_convert_greyscale", expand=True)
            row = layout.row()
            row.prop(scene, "TC_smart_resize", expand=True)
            row = layout.row()
            row.prop(scene, "TC_optimize_float", expand=True)
            row = layout.row()

            col = row.split(factor=0.9)
            factor = after / before if before != 0 else 0
            text = f"Before: {int(before)}MB | After: {int(after)}MB | Savings: {int(delta)}MB"
            text = f"{int(before)}MB -> {int(after)}MB = {int(delta)}MB saved in {num_of_changes} textures"
            col.progress(factor=factor, text=text)

            col.operator("texture_compactor.show_report", text="", icon="FILE")

            row = layout.row()
            if num_of_changes == 0:
                text = "No textures to optimize"
                row.enabled = False
            elif is_optimized:
                text = "All textures are already optimized"
                row.enabled = False
            else:
                text = f"Optimize {num_of_changes} Textures"
            row.operator("texture_compactor.optimize_textures", text=text, icon="PLAY")


class TEXCOMPACTOR_OT_scan_textures(bpy.types.Operator):
    bl_label = "Scan All Textures"
    bl_idname = "texture_compactor.scan_textures"
    bl_description = "Scan all textures in the scene and look for optimization opportunities"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    _timer = None
    _executor = None
    _futures = None
    _progress = 0
    _total_images = 0

    def scan_image(self, img):
        # Skip non-pixel types like viewer nodes or render result
        if img.type != "IMAGE":
            print(f"Skipping {img} ({img.type})")
            return None

        # Ensure image is loaded by accessing its size first
        w, h = img.size

        if w == 0 or h == 0:
            print(f"Image {img} is not loaded")
            return None

        if not img.has_data:
            print(f"Image {img.name} has no pixel data")
            return None

        users = bpy.data.user_map(subset=[img])
        if not users[img]:
            print(f"Skipping orphan {img}")
            return None

        # Do the actual scan and return the metadata
        return core.scan_image(img)

    def modal(self, context, event):
        wm = context.window_manager
        if event.type == "TIMER":
            if self._futures:
                done, not_done = concurrent.futures.wait(
                    self._futures, timeout=0, return_when=concurrent.futures.FIRST_COMPLETED
                )
                for future in done:
                    try:
                        img_info = future.result()
                        if img_info is not None:
                            context.scene.TC_texture_metadata.append(img_info)
                    except Exception as exc:
                        print(f"Exception during scanning: {exc}")
                    self._futures.remove(future)
                    self._progress += 1

                # Update the progress bar
                progress_percentage = (self._progress / self._total_images) * 100
                wm.progress_update(self._progress)
                self.report(
                    {"INFO"}, f"Scanning progress: {self._progress}/{self._total_images} ({int(progress_percentage)}%)"
                )

                if not self._futures:  # Only shut down if all futures are done
                    self._executor.shutdown(wait=False)
                    context.window_manager.event_timer_remove(self._timer)
                    self.report({"INFO"}, "Scanning completed.")

                    core.update_memory_usage(self, context)
                    wm.progress_end()

                    if settings.AUTO_SHOW_REPORT:
                        core.show_report(context.scene.TC_texture_metadata)

                    packed = core.tally_packed(context.scene.TC_texture_metadata)
                    if packed:
                        # pop up a confirmation modal
                        self.report(
                            {"ERROR"},
                            f"{packed} packed textures cannot be optimized. Please unpack them before optimizing.",
                        )

                    return {"FINISHED"}

        return {"PASS_THROUGH"}

    def execute(self, context):
        # warn if the user is scanning when using optimzied textures
        if context.scene.TC_texture_swap == "1":
            self.report(
                {"ERROR"},
                "You are already using optimized textures. Please switch to the original textures first.",
            )
            return {"CANCELLED"}

        start = time.time()
        context.scene.TC_texture_metadata.clear()

        self._executor = concurrent.futures.ThreadPoolExecutor()
        self._futures = [self._executor.submit(self.scan_image, img) for img in bpy.data.images]
        self._total_images = len(self._futures)

        wm = context.window_manager
        wm.progress_begin(0, self._total_images)
        self._timer = wm.event_timer_add(0.1, window=context.window)
        wm.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def cancel(self, context):
        if self._executor:
            self._executor.shutdown(wait=False)
        if self._timer:
            context.window_manager.event_timer_remove(self._timer)
        context.window_manager.progress_end()
        self.report({"INFO"}, "Scanning canceled.")
        return {"CANCELLED"}


class TEXCOMPACTOR_OT_optimize_textures(bpy.types.Operator):
    bl_label = "Optimize Textures"
    bl_idname = "texture_compactor.optimize_textures"
    bl_description = "Optimize all textures used in the scene using the settings above"

    def execute(self, context):
        # core.update_memory_usage(self, context)
        core.optimize_images(self, context)
        # core.update_memory_usage(self, context)
        return {"FINISHED"}


class TEXCOMPACTOR_OT_show_report(bpy.types.Operator):
    bl_label = "Show Detailed Report"
    bl_idname = "texture_compactor.show_report"
    bl_description = "Show a detailed HTML report of all textures in the scene in the web browser"

    def execute(self, context):
        core.show_report(context.scene.TC_texture_metadata)
        return {"FINISHED"}
