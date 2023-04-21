###################################################################################
#MIT License
#
#Copyright (c) 2023 Miro Creative, LLC
#
#Permission is hereby granted, free of charge, to any person obtaining a copy
#of this software and associated documentation files (the "Software"), to deal
#in the Software without restriction, including without limitation the rights
#to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#copies of the Software, and to permit persons to whom the Software is
#furnished to do so, subject to the following conditions:
#
#The above copyright notice and this permission notice shall be included in all
#copies or substantial portions of the Software.
#
#THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
#SOFTWARE.
###################################################################################

import hou


def copy_texture_file_path(shader_node, parm_name, tex_node):
    parm = shader_node.parm(parm_name)
    if parm:
        tex_file = parm.eval()
        if tex_file:
            tex_node.parm("A_FILENAME").set(tex_file)


def process_material_builder(mat_builder, mat_network):
    # Rename the Principled Shader inside the Material Builder node
    principled_shader = mat_builder.node("principledshader1")
    if not principled_shader:
        raise ValueError(
            f"No Principled Shader found inside the Material Builder node: {mat_builder.name()}"
        )
    new_shader_name = mat_builder.name()
    # Copy the renamed Principled Shader to the /mat network
    copied_shader = mat_network.createNode("principledshader", new_shader_name)
    for p in principled_shader.parms():
        if p.isAtDefault() or p.name() in ("vm_filename", "ogl_tex1"):
            continue
        copied_shader.parm(p.name()).set(p.eval())

    # Create a new octane_vopnet in the /mat network with the copied Principled Shader's name
    new_octane_vopnet = mat_network.createNode(
        "octane_vopnet", f"{new_shader_name}_octane"
    )
    if new_octane_vopnet.parm("ogl_numtex"):
        new_octane_vopnet.parm("ogl_numtex").set(1)
        new_octane_vopnet.parm("ogl_tex1").set('`chs("BaseColor/A_FILENAME")`')

    # Get the existing Standard_Surface node inside the octane_vopnet, if any
    standard_surface = new_octane_vopnet.node("Standard_Surface")
    if not standard_surface:
        # Create the new Standard_Surface node inside the octane_vopnet
        standard_surface = new_octane_vopnet.createNode(
            "octane::NT_MAT_STANDARD_SURFACE"
        )
        standard_surface.setName("Standard_Surface")

    # Create new octane::NT_TEX_IMAGE nodes for BaseColor, Roughness, and Normal inside the octane_vopnet
    tex_nodes = {}
    for tex_name in ("BaseColor", "Roughness", "Normal"):
        tex_node = new_octane_vopnet.createNode("octane::NT_TEX_IMAGE")
        tex_node.setName(tex_name)
        tex_nodes[tex_name] = tex_node

    # Connect the output of the texture nodes to the input of the Standard_Surface node
    standard_surface.setInput(1, tex_nodes["BaseColor"], 0)
    standard_surface.setInput(6, tex_nodes["Roughness"], 0)
    standard_surface.setInput(44, tex_nodes["Normal"], 0)

    # Copy the texture file paths from the original Principled Shader to the octane::NT_TEX_IMAGE nodes
    copy_texture_file_path(copied_shader, "basecolor_texture", tex_nodes["BaseColor"])
    copy_texture_file_path(copied_shader, "rough_texture", tex_nodes["Roughness"])
    copy_texture_file_path(copied_shader, "baseNormal_texture", tex_nodes["Normal"])
    tex_nodes["Roughness"].parm("colorSpace").set("NAMED_COLOR_SPACE_OTHER")
    tex_nodes["Normal"].parm("colorSpace").set("NAMED_COLOR_SPACE_OTHER")

    # Check if the original Principled Shader has a metallic texture enabled and create a new octane::NT_TEX_IMAGE node if so
    if copied_shader.parm("metallic_texture").eval():
        tex_nodes["Metallic"] = new_octane_vopnet.createNode("octane::NT_TEX_IMAGE")
        tex_nodes["Metallic"].setName("Metallic")
        tex_nodes["Metallic"].parm("colorSpace").set("NAMED_COLOR_SPACE_OTHER")
        # Connect the output of the Transparency node to the input of the Standard_Surface node
        standard_surface.setInput(3, tex_nodes["Metallic"], 0)
        # Copy the texture file path from the original Principled Shader to the octane::NT_TEX_IMAGE node
        copy_texture_file_path(copied_shader, "metallic_texture", tex_nodes["Metallic"])

    # Check if the original Principled Shader has an emission color texture enabled and create a new octane::NT_TEX_IMAGE node if so
    if copied_shader.parm("emitcolor_texture").eval():
        tex_nodes["Emission"] = new_octane_vopnet.createNode("octane::NT_TEX_IMAGE")
        tex_nodes["Emission"].setName("Emission_Color")
        # Connect the output of the Transparency node to the input of the Standard_Surface node
        standard_surface.setInput(38, tex_nodes["Emission"], 0)
        # Set Emission Color weight
        standard_surface.parm("emissionWeight").set(1)
        # Copy the texture file path from the original Principled Shader to the octane::NT_TEX_IMAGE node
        copy_texture_file_path(
            copied_shader, "emitcolor_texture", tex_nodes["Emission"]
        )

    # Check if the original Principled Shader has a displacement map enabled and create a new octane::NT_DISPLACEMENT node if so
    if copied_shader.parm("dispTex_enable").eval():
        displacement_node = new_octane_vopnet.createNode("octane::NT_DISPLACEMENT")
        displacement_node.setName("Displacement1")
        disp_tex_image = new_octane_vopnet.createNode("octane::NT_TEX_IMAGE")
        disp_tex_image.setName("Displacement")
        disp_tex_image.parm("colorSpace").set("NAMED_COLOR_SPACE_OTHER")
        copy_texture_file_path(copied_shader, "dispTex_texture", disp_tex_image)
        displacement_node.setInput(0, disp_tex_image, 0)
        standard_surface.setInput(45, displacement_node, 0)

    # Check if the original Principled Shader has a transparency map enabled and create a new octane::NT_TEX_IMAGE node if so
    if copied_shader.parm("opaccolor_useTexture").eval():
        octane_transparency = new_octane_vopnet.createNode("octane::NT_TEX_IMAGE")
        octane_transparency.setName("Opacity")
        octane_transparency.parm("colorSpace").set("NAMED_COLOR_SPACE_OTHER")

        # Connect the output of the Transparency node to the input of the Standard_Surface node
        standard_surface.setInput(49, octane_transparency, 0)

        # Copy the texture file path from the original Principled Shader to the octane::NT_TEX_IMAGE node
        copy_texture_file_path(
            copied_shader, "opaccolor_texture", octane_transparency
        )


def rename_octane_material_builders(network):
    octane_material_builders = [
        node for node in network.children() if node.type().name() == "octane_vopnet"
    ]
    for builder in octane_material_builders:
        builder.setName(builder.name().replace("_octane", ""), unique_name=True)


def delete_principled_shaders(network):
    principled_shaders = [
        node
        for node in network.children()
        if node.type().name() == "principledshader::2.0"
    ]
    for shader in principled_shaders:
        shader.destroy()


# Get the selected Material Builder nodes
selected_nodes = hou.selectedNodes()
if not selected_nodes:
    raise ValueError("Please select at least one Material Builder node.")

mat_network = hou.node("/mat")
if not mat_network:
    raise ValueError("Unable to find the /mat network.")

for node in selected_nodes:
    if node.type().name() != "materialbuilder":
        raise ValueError(
            f"Please select only Material Builder nodes. Found {node.type().name()} node: {node.name()}"
        )
    process_material_builder(node, mat_network)

# Delete all principledshader::2.0 nodes in the /mat network
delete_principled_shaders(mat_network)

# Rename all Octane Material Builder nodes in the /mat network
rename_octane_material_builders(mat_network)
