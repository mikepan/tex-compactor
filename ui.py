import time
import concurrent.futures

import bpy

from texturecompactor import core
from texturecompactor import pro


class TEXTURECOMPACTOR_PT_main_panel(bpy.types.Panel):
    bl_label = "Texture Compactor"
    bl_idname = "TEXTURECOMPACTOR_PT_main_panel"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "render"

    def draw(self, context):
        layout = self.layout
        layout.use_property_split = True
        scene = context.scene

        has_data = bool(context.scene.TC_texture_metadata)

        # always show
        col = layout.column()
        col.operator("texture_compactor.scan_textures", icon="FILE_REFRESH")

        # bail early if scanning isn't done
        if not has_data:
            return

        # show the rest of the UI after scanning is done
        before, after, delta, num_of_changes = core.tally_sizes(context.scene.TC_texture_metadata)
        is_optimized = core.is_optimized(context.scene.TC_texture_metadata)

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

        # UI after optimizing
        if is_optimized:
            row = layout.row()
            row.prop(scene, "TC_texture_swap", expand=True)
            row = layout.row()


class TEXTURECOMPACTOR_OT_scan_textures(bpy.types.Operator):
    bl_label = "Scan All Textures"
    bl_idname = "texture_compactor.scan_textures"
    bl_description = "Scan all textures in the scene and look for optimization opportunities"

    def scan_image(self, img):
        # Skip non-pixel types like viewer nodes or render result
        if img.type != "IMAGE":
            print(f"Skipping {img} ({img.type})")
            return None

        # Ensure image is loaded by accessing its size first
        w, h = img.size

        # Error on non-loaded images
        if w == 0 or h == 0:
            print(f"Image {img} is not loaded")
            return None

        if not img.has_data:
            print(f"Image {img.name} has no pixel data")
            return None

        # Skip images that are not used
        users = bpy.data.user_map(subset=[img])
        if not users[img]:
            print(f"Skipping orphan {img}")
            return None

        # Do the actual scan and return the metadata
        return core.scan_image(img)

    def execute(self, context):
        start = time.time()

        context.scene.TC_texture_metadata.clear()

        # Create a thread pool
        with concurrent.futures.ThreadPoolExecutor() as executor:
            # Submit tasks for each image
            future_to_img = {executor.submit(self.scan_image, img): img for img in bpy.data.images}

            # Collect results as they complete
            for future in concurrent.futures.as_completed(future_to_img):
                img = future_to_img[future]
                try:
                    img_info = future.result()
                    if img_info is not None:
                        context.scene.TC_texture_metadata.append(img_info)
                except Exception as exc:
                    print(f"{img} generated an exception: {exc}")

        end = time.time()
        print(f"Scanning took {end - start:.1f} seconds")

        # Update estimated memory usage
        core.update_memory_usage(self, context)

        return {"FINISHED"}


class TEXTURECOMPACTOR_OT_optimize_textures(bpy.types.Operator):
    bl_label = "Optimize Textures"
    bl_idname = "texture_compactor.optimize_textures"
    bl_description = "Optimize all textures used in the scene using the settings above"

    def execute(self, context):
        pro.optimize_textures(self, context)
        return {"FINISHED"}


class TEXTURECOMPACTOR_OT_show_report(bpy.types.Operator):
    bl_label = "Show Detailed Report"
    bl_idname = "texture_compactor.show_report"
    bl_description = "Show a detailed HTML report of all textures in the scene in the web browser"

    def execute(self, context):
        filename = bpy.path.abspath(f"//{bpy.data.filepath}_texture_compactor_report.html")
        core.show_report(context.scene.TC_texture_metadata, filename)
        return {"FINISHED"}
