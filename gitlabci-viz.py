import yaml
import networkx as nx
import matplotlib.pyplot as plt
from networkx.drawing.nx_agraph import graphviz_layout
from matplotlib.patches import Patch
import numpy as np
import os
from pathlib import Path

def parse_includes(data, base_dir='.'):
    """Recursively parse and process included files."""
    if isinstance(data, dict):
        if 'include' in data:
            includes = data['include']
            if not isinstance(includes, list):
                includes = [includes]

            for include in includes:
                if isinstance(include, dict) and 'local' in include:
                    include_path = os.path.join(base_dir, include['local'])
                    with open(include_path, 'r') as file:
                        included_data = yaml.safe_load(file)
                        # Process nested includes
                        included_data = parse_includes(included_data, os.path.dirname(include_path))
                        # Merge the included data
                        data.update({k: v for k, v in included_data.items() if k != 'include'})

            # Remove the include directive after processing
            del data['include']

    return data

def parse_gitlab_ci_yaml(file_path):
    """Parse the GitLab CI YAML file and return a dictionary."""
    with open(file_path, 'r') as file:
        data = yaml.safe_load(file)
        base_dir = os.path.dirname(os.path.abspath(file_path))
        return parse_includes(data, base_dir)

def build_graph(data):
    """Build a graph from the parsed YAML data."""
    graph = nx.DiGraph()

    # First pass: add all nodes
    for job_name in data.keys():
        if job_name.startswith('.'):  # Template/Hidden job
            graph.add_node(job_name,
                         type='hidden',
                         label=job_name,
                         color='#E3F2FD',  # Light blue
                         shape='s',
                         edge_color='#1976D2')  # Darker blue for edges
        else:  # Regular job
            graph.add_node(job_name,
                         type='job',
                         label=job_name,
                         color='#E8F5E9',  # Light green
                         shape='o',
                         edge_color='#388E3C')  # Darker green for edges

    # Second pass: add edges for extends
    for job_name, job_config in data.items():
        if isinstance(job_config, dict) and 'extends' in job_config:
            extends = job_config['extends']
            if isinstance(extends, str):
                extends = [extends]

            if isinstance(extends, list):
                for parent in extends:
                    # Add missing nodes (templates from includes)
                    if parent not in graph:
                        graph.add_node(parent,
                                     type='hidden',
                                     label=parent,
                                     color='#E3F2FD',
                                     shape='s',
                                     edge_color='#1976D2')

                    # Add the edge
                    graph.add_edge(parent, job_name, label='extends')

    return graph

def get_edge_connection_points(pos, node1, node2, graph):
    """Calculate the exact connection points for edges on the shapes."""
    x1, y1 = pos[node1]
    x2, y2 = pos[node2]

    # Calculate angle between nodes
    angle = np.arctan2(y2 - y1, x2 - x1)

    # Adjust start and end points based on shape
    if graph.nodes[node1]['shape'] == 's':  # Rectangle
        width, height = 60, 30
        # Find intersection point with rectangle
        if abs(np.cos(angle)) * height > abs(np.sin(angle)) * width:
            # Intersects with vertical sides
            tx = width/2 * np.sign(np.cos(angle))
            ty = tx * np.tan(angle)
        else:
            # Intersects with horizontal sides
            ty = height/2 * np.sign(np.sin(angle))
            tx = ty / np.tan(angle) if np.tan(angle) != 0 else width/2
        start_x = x1 + tx
        start_y = y1 + ty
    else:  # Circle
        radius = 20
        start_x = x1 + radius * np.cos(angle)
        start_y = y1 + radius * np.sin(angle)

    # Calculate end point
    if graph.nodes[node2]['shape'] == 's':  # Rectangle
        width, height = 60, 30
        angle_end = angle + np.pi  # Reverse angle for end point
        if abs(np.cos(angle_end)) * height > abs(np.sin(angle_end)) * width:
            tx = width/2 * np.sign(np.cos(angle_end))
            ty = tx * np.tan(angle_end)
        else:
            ty = height/2 * np.sign(np.sin(angle_end))
            tx = ty / np.tan(angle_end) if np.tan(angle_end) != 0 else width/2
        end_x = x2 + tx
        end_y = y2 + ty
    else:  # Circle
        radius = 20
        end_x = x2 + radius * np.cos(angle + np.pi)
        end_y = y2 + radius * np.sin(angle + np.pi)

    return (start_x, start_y), (end_x, end_y)

def visualize_graph(graph):
    """Visualize the graph with enhanced styling and improved arrow connections."""
    plt.figure(figsize=(12, 8))

    # Use hierarchical layout with increased spacing
    pos = graphviz_layout(graph, prog='dot', args='-Gnodesep=0.5 -Granksep=1.0')

    # Draw nodes with custom styling
    for node in graph.nodes:
        node_attrs = graph.nodes[node]
        if node_attrs['shape'] == 's':  # Hidden jobs (rectangles)
            plt.gca().add_patch(plt.Rectangle(
                (pos[node][0] - 30, pos[node][1] - 15),
                60, 30,
                facecolor=node_attrs['color'],
                edgecolor=node_attrs['edge_color'],
                linewidth=2,
                alpha=0.9,
                zorder=1
            ))
        else:  # Regular jobs (circles)
            plt.gca().add_patch(plt.Circle(
                (pos[node][0], pos[node][1]),
                radius=20,
                facecolor=node_attrs['color'],
                edgecolor=node_attrs['edge_color'],
                linewidth=2,
                alpha=0.9,
                zorder=1
            ))

    # Draw edges with custom connection points
    for edge in graph.edges():
        start_node, end_node = edge
        start_point, end_point = get_edge_connection_points(pos, start_node, end_node, graph)

        # Draw the arrow
        plt.arrow(
            start_point[0], start_point[1],
            end_point[0] - start_point[0], end_point[1] - start_point[1],
            head_width=8, head_length=10,
            fc='#616161', ec='#616161',
            length_includes_head=True,
            alpha=0.6,
            zorder=0
        )

    # Draw edge labels with better positioning
    edge_labels = nx.get_edge_attributes(graph, 'label')
    nx.draw_networkx_edge_labels(graph, pos,
                               edge_labels=edge_labels,
                               font_size=8,
                               font_family='sans-serif',
                               font_weight='bold',
                               bbox=dict(facecolor='white',
                                       edgecolor='none',
                                       alpha=0.7,
                                       pad=0.5))

    # Draw node labels
    labels = nx.get_node_attributes(graph, 'label')
    nx.draw_networkx_labels(graph, pos,
                          labels=labels,
                          font_size=10,
                          font_weight='bold',
                          font_family='sans-serif')

    # Create custom legend
    legend_elements = [
        Patch(facecolor='#E8F5E9', edgecolor='#388E3C',
              label='Jobs', alpha=0.9),
        Patch(facecolor='#E3F2FD', edgecolor='#1976D2',
              label='Templates', alpha=0.9)
    ]
    plt.legend(handles=legend_elements,
              loc='upper right',
              frameon=True,
              fancybox=True,
              shadow=True,
              fontsize=10)

    # Set title with custom styling
    plt.title("GitLab CI Job Dependencies",
             fontsize=14,
             fontweight='bold',
             pad=20,
             fontfamily='sans-serif')

    # Adjust layout and display
    plt.axis('off')
    plt.tight_layout()
    plt.margins(0.2)
    plt.show()

def main():
    file_path = '.gitlab-ci.yml'
    data = parse_gitlab_ci_yaml(file_path)
    graph = build_graph(data)
    visualize_graph(graph)

if __name__ == '__main__':
    main()