#!/usr/bin/env python

import argparse
import itertools
import networkx
import trimesh

def load_mesh(filename):
    mesh = trimesh.load(filename)
    mesh.fix_normals()
    return mesh

def route_string(mesh, elide_facets=True):
    # face id -> primary face id
    facet_map = {x: x for x in range(len(mesh.faces))}
    if elide_facets:
        for facet in mesh.facets:
            for face in facet:
                facet_map[face] = facet[0]

    # (facet id, edge) -> (facet id, edge)
    connectivity = {}
    # (face id, edge) -> (face id, edge)
    facet_edges = {}
    for face, vertices in enumerate(mesh.faces):
        assert len(vertices) == 3
        facet = facet_map[face]
        for i in range(3):
            for d in (-1, 1):
                j = (i + d) % 3
                k = (i + d * 2) % 3
                v1, v2, v3 = vertices[i], vertices[j], vertices[k]
                connectivity[(facet, (v1, v2))] = (facet, (v2, v3))
                facet_edges[(face, (v1, v2))] = (face, (v2, v3))

    graph = networkx.Graph()
    for face_pair, raw_edge in zip(mesh.face_adjacency, mesh.face_adjacency_edges):
        f1, f2 = [facet_map[f] for f in face_pair]
        edge = tuple(sorted(raw_edge))
        if f1 == f2:
            # Same facet, so elide the shared edge from connectivity
            for shared_edge in (edge, edge[::-1]):
                _f1, adj_edge1 = facet_edges[(face_pair[0], shared_edge)]
                _f2, adj_edge2 = facet_edges[(face_pair[1], shared_edge)]
                connectivity[(f1, adj_edge1[::-1])] = (f2, adj_edge2)
                connectivity[(f2, adj_edge2[::-1])] = (f1, adj_edge1)
                facet_edges[(_f1, adj_edge1[::-1])] = (face_pair[1], adj_edge2)
                facet_edges[(_f2, adj_edge2[::-1])] = (face_pair[0], adj_edge1)
        else:
            graph.add_edge(f1, f2, shared_edge=edge)

    # minimum_spanning_tree is overkill, we just need *any* spanning tree
    for face_pair in networkx.minimum_spanning_tree(graph).edges:
        f1, f2 = [facet_map[f] for f in face_pair]
        edge = graph.edges[face_pair]["shared_edge"]
        # cross strings at each shared edge in the spanning tree
        for shared_edge in (edge, edge[::-1]):
            fe1 = connectivity[(f1, shared_edge)]
            fe2 = connectivity[(f2, shared_edge)]
            connectivity[(f1, shared_edge)] = fe2
            connectivity[(f2, shared_edge)] = fe1
            first_step = fe1

    # Follow the connectivity to produce a stepwise path
    # Each step is (face, (from_vertex, to_vertex))
    # The string will pass through each edge twice
    steps = []
    step = first_step
    while True:
        steps.append(step)
        step = connectivity.pop(step)
        if step == first_step:
            break
    steps.append(step)

    return steps

def index_to_name(index):
    name = ""
    while True:
        name = chr(ord('A') + (index % 26)) + name
        if index < 26:
            break
        index //= 26
        index -= 1
    return name

def print_steps(mesh, steps, scale=1.0):
    pipes = {}
    for _face, edge in steps:
        if edge in pipes or edge[::-1] in pipes:
            continue
        i = len(pipes)
        head = mesh.vertices[edge[1]]
        tail = mesh.vertices[edge[0]]
        length = sum([(a - b) ** 2. for a, b in zip(head, tail)]) ** 0.5
        length = round(length * scale, 3)
        pipes[edge] = {
            "name": index_to_name(i),
            "length": length,
            "sort_order": (length, i),
            "new": True
        }
    print "Bill of Materials"
    print "================="
    for pipe in sorted(pipes.values(), key=lambda x: x["sort_order"]):
        print "Pipe {:>3}, length={}".format(pipe["name"], pipe["length"])

    print ""
    print "Total length:", sum([p["length"] for p in pipes.values()])

    print ""
    print "Assembly Steps"
    print "=============="
    for i, (face, edge) in enumerate(steps):
        flip = False
        if edge not in pipes:
            edge = edge[::-1]
            flip = True
        pipe = pipes[edge]
        print "Step {:>3}: into pipe {} {} {}".format(i + 1, pipe["name"], ["front", "back"][flip], ["", "(new)"][pipe["new"]])
        pipe["new"] = False
    print "          ...and tie off"


def main():
    parser = argparse.ArgumentParser(description="Convert STL meshes into a series of steps to assemble from pipes and string")
    parser.add_argument("filename", nargs="?", help="Input STL file")
    parser.add_argument("--verbose", "-v", action="store_true", help="Include trimesh debug log")
    parser.add_argument("--elide-facets", "-f", action="store_true", help="Elide edges shared by coplanar faces, reducing structure stability")
    parser.add_argument("--scale", "-s", default=1.0, type=float, help="Scale factor")
    parser.add_argument("--preview", "-p", action="store_true", help="Show 3D preview of input mesh")

    parser.add_argument("--box", action="store_true", help="Use a box (cube) as the input mesh")
    parser.add_argument("--icosahedron", action="store_true", help="Use an icosahedron as the input mesh")
    parser.add_argument("--annulus", metavar="N", type=int, help="Use an annulus with N sides as the input mesh")

    args = parser.parse_args()

    if args.verbose:
        trimesh.util.attach_to_log()

    if args.box:
        mesh = trimesh.primitives.Box()
    elif args.icosahedron:
        mesh = trimesh.creation.icosahedron()
    elif args.annulus is not None:
        mesh = trimesh.creation.annulus(sections=args.annulus+1)
    elif args.filename:
        mesh = load_mesh(args.filename)
    else:
        parser.error("Must specify filename or shape")

    assert mesh

    steps = route_string(mesh, elide_facets=args.elide_facets)
    print_steps(mesh, steps, scale=args.scale)

    if args.preview:
        viewer = mesh.show(start_loop=False)
        viewer.view["wireframe"] = True
        viewer.view["cull"] = False
        viewer.update_flags()

        import pyglet
        pyglet.app.run()

    return mesh, steps

if __name__ == "__main__":
    mesh, steps = main()
