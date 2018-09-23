import numpy
import stl
from mpl_toolkits import mplot3d
from matplotlib import pyplot
from collections import defaultdict

def show_mesh(mesh):
    figure = pyplot.figure()
    axes = mplot3d.Axes3D(figure)

    axes.add_collection(mplot3d.art3d.Poly3DCollection(mesh.vectors))

    # Auto scale
    scale = mesh.points.flatten(-1)
    axes.auto_scale_xyz(scale, scale, scale)

    pyplot.show()

def load_mesh(filename):
    mesh = stl.mesh.Mesh.from_file(filename)
    mesh.update_normals()
    return mesh

def mesh_to_edges(mesh):
    # Map of (v1, v2) -> {"faces": (face_idx1, face_idx2)}
    # Edges are normalized s.t. v1 <= v2
    initial_edges = defaultdict(list)
    for face_idx, edge_list in enumerate(mesh.data["vectors"]):
        # 1-index faces, use negative to mean edge is inverted
        face_idx += 1
        assert len(edge_list) > 2

        for i in range(len(edge_list)):
            v1, v2 = tuple(edge_list[i]), tuple(edge_list[i-1])
            if v2 < v1:
                v1, v2 = v2, v1
                face_idx = -face_idx
            initial_edges[(v1, v2)].append(face_idx)

    open_edges = []
    edges = {}
    for edge, faces in initial_edges.items():
        assert len(faces) == 2
        #assert faces[0] * faces[1] < 0, faces
        edges[edge] = {"faces": tuple(sorted(faces))}

    return edges

def populate_edge_metadata(edges, scale=1.0):
    assert scale > 0.

    for edge, props in edges.items():
        props["length"] = scale * sum([(a - b) ** 2 for a, b in zip(*edge)]) ** 0.5
        props["steps"] = []

    for index, (edge, props) in enumerate(sorted(edges.items(), key=lambda x: x[1]["length"])):
        props["index"] = index
        props["name"] = "#{} ({} cm)".format(index, scale)

def calculate_spanning_tree(edges):
    covered_faces = set()
    covered_faces.add(1)

    for props in edge.values():
        if all([abs(f) in covered_faces for f in props["faces"]]):
            props["in_spanning_tree"] = False
        else:
            props["in_spanning_tree"] = True
            for f in props["faces"]:
                covered_faces.add(abs(f))

def next_edge(mesh, edge, face_idx):
    if face_idx < 0:
        v2, v1 = edge
    else:
        v1, v2 = edge
    edge_list = mesh.data["vectors"]
    for idx, vedge in enumerate(edge_list):
        if tuple(vedge) == v2:
            result = tuple(edge_list[idx-1])
            assert result != v1
            return (v1, result)
    raise Exception(face_idx)

def generate_build_steps(mesh, edges):
    steps = []
    # Starting edge
    edge = edges.keys()[0]
    while True:
        assert len(edges[edge]["steps"]) < 2
        edges[edge]["steps"].append(len(steps))
        steps.append(edges[edge])
        if len(steps) == len(edges) * 2:
            break
        use_face_2 = (len(edges[edge]["steps"]) == 2) ^ (edges[edge]["in_spanning_tree"])
        next_face_idx = edges[edge]["faces"][2 if use_face_2 else 1]
        edge = next_edge(mesh, edge, next_face_idx)
    return steps

def print_build_steps(steps):
    for edge in steps:
        print edge["name"]

def main():
    m = load_mesh("test/prism.stl")
    return m
    #show_mesh(m)
    edges = mesh_to_edges(m)
    return edges
    populate_edge_metadata(edges)
    calculate_spanning_tree(edges)
    steps = generate_build_steps(mesh, edges)
    print_build_steps(steps)
    return edges, steps

if __name__ == "__main__":
    m = main()
