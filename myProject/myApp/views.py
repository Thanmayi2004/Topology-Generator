from django.shortcuts import render
from django.core.files.storage import default_storage
from django.http import HttpResponse
from .forms import UploadFileForm
import yaml
import networkx as nx
from django.http import JsonResponse
import base64
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
import io
import os
from django.conf import settings
from django.templatetags.static import static
from .models import FileUploadHistory
from django.shortcuts import render, redirect
from django.db import transaction
from django.utils.timezone import now

def handle_uploaded_file(f, username):
    file_path = os.path.join('uploads', f'{username}_{f.name}')
    with open(file_path, 'wb+') as destination:
        for chunk in f.chunks():
            destination.write(chunk)
    return file_path
    
def parse_yaml(file_path):
    with open(file_path, 'r') as file:
        try:
            return yaml.safe_load(file)
        except yaml.YAMLError as exc:
            print(f"Error parsing YAML: {exc}")
            return None

def save_graph_image(G, username):
    buf = io.BytesIO()
    plot_topology(G, buf)
    image_data = buf.getvalue()

    file_name = f'{username}_{now().strftime("%Y%m%d_%H%M%S")}.png'
    file_path = os.path.join(settings.MEDIA_ROOT, 'graphs', file_name)
    
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    
    with open(file_path, 'wb') as f:
        f.write(image_data)

    print(f"Saved graph image to: {file_path}")
    return os.path.join('graphs', file_name)  # Return path relative to MEDIA_ROOT

def home(request):
    images = [
        '/RouterBlue.png',
        '/SwitchBlue.png',
        '/firewall.png',
        '/cloud-computing.png',
        '/FRSW.png',
        '/HubBlue.png',
        '/desktop.png'
    ]
    return render(request, 'myApp/home.html', {'images': images})

def upload_history(request):
    history = FileUploadHistory.objects.all()
    print(history) 
    return render(request, 'myApp/upload_history.html', {'history': history})

def upload_file(request):
    if request.method == 'POST':
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                with transaction.atomic():
                    # Handle file upload
                    file_path = handle_uploaded_file(request.FILES['file'], request.user.username)
                    
                    # Parse YAML content
                    yaml_data = parse_yaml(file_path)
                    if yaml_data is None:
                        raise ValueError("Invalid YAML file")

                    # Generate the graph and save it
                    G = create_topology_graph(yaml_data)
                    graph_file_name = save_graph_image(G, request.user.username)

                    # Save history to database
                    FileUploadHistory.objects.create(
                        user=request.user,
                        input_file=request.FILES['file'].name,
                        graph_url=graph_file_name
                    )

                    return redirect('upload_file')  # or return the URL of the page to display the graph
            except Exception as e:
                print(f"Error: {e}")
                return render(request, 'upload_file.html', {
                    'form': form,
                    'error_message': str(e)
                })
    else:
        form = UploadFileForm()

    upload_history = FileUploadHistory.objects.filter(user=request.user).order_by('-upload_time')
    return render(request, 'upload_file.html', {'form': form, 'upload_history': upload_history})

def serve_graph_image(request, id):
    try:
        file_record = FileUploadHistory.objects.get(id=id)
        file_path = os.path.join(settings.MEDIA_ROOT, file_record.graph_url)
        with open(file_path, 'rb') as f:
            return HttpResponse(f.read(), content_type="image/png")
    except FileUploadHistory.DoesNotExist:
        return HttpResponse("File not found", status=404)
    except FileNotFoundError:
        return HttpResponse("File not found on server", status=404)


def get_device_type(device_name):
    if device_name.startswith('R'):
        return 'Router'
    elif device_name.startswith('PC'):
        return 'PC'
    elif device_name.startswith('S'):
        return 'Switch'
    elif device_name.startswith('NAT'):
        return 'NAT'
    elif device_name.startswith('H'):
        return 'Hub'
    elif device_name.startswith('Cloud'):
        return 'Cloud'
    elif device_name.startswith('Firewall'):
        return 'Firewall'
    elif device_name.startswith('FRSW'):
        return 'FRSW'
    else:
        return 'Other'
    

def create_topology_graph(data):
    G = nx.DiGraph()
    for device, connections in data.items():
        device_type = get_device_type(device)
        G.add_node(device, type=device_type)
        for port, connected_device in connections.items():
            if G.has_edge(device, connected_device):
                G.edges[device, connected_device]['labels'][device] = port
            else:
                G.add_edge(device, connected_device, labels={device: port}, color='black', alpha=1)
    return G

def plot_topology(G, buf):
    # Adjust the figure size (width, height) to make the graph smaller
    fig, ax = plt.subplots(figsize=(10, 8))  
    
    pos = nx.spring_layout(G)  
    
    # Draw edges
    for u, v, attributes in G.edges(data=True):
        nx.draw_networkx_edges(G, pos, edgelist=[(u, v)], edge_color=attributes['color'], alpha=attributes['alpha'], ax=ax)
    
    # Draw nodes with images
    for node, node_type in nx.get_node_attributes(G, 'type').items():
        img_path = determine_image_path(node_type)
        # Generate the absolute file path
        abs_img_path = os.path.join(settings.BASE_DIR, 'static', img_path)
        try:
            img = mpimg.imread(abs_img_path)  
        except FileNotFoundError:
            print(f"Image file not found: {abs_img_path}")
            continue
        
        icon_size = determine_icon_size(node_type)
        fontsize, fontweight, color = determine_font_attributes(node_type)
        
        if img_path is not None:
            imagebox = OffsetImage(img, zoom=icon_size)
            ab = AnnotationBbox(imagebox, pos[node], frameon=False, box_alignment=(0.5, 0.5), zorder=2)
            ax.add_artist(ab)
        
        ax.text(pos[node][0], pos[node][1], node, ha='center', va='center', fontsize=fontsize, fontweight=fontweight, color=color, zorder=3)
    
    # Draw edge labels
    for u, v, attributes in G.edges(data=True):
        u_port = attributes['labels'].get(u, '')
        v_port = attributes['labels'].get(v, '')
        u_label_pos = (0.70 * pos[u][0] + 0.25 * pos[v][0], 0.70 * pos[u][1] + 0.25 * pos[v][1])
        v_label_pos = (0.70 * pos[v][0] + 0.25 * pos[u][0], 0.70 * pos[v][1] + 0.25 * pos[u][1])
        ax.text(u_label_pos[0], u_label_pos[1], u_port, fontsize=6, ha='center', va='center', color='black', zorder=4)
        ax.text(v_label_pos[0], v_label_pos[1], v_port, fontsize=6, ha='center', va='center', color='black', zorder=4)
    
    plt.axis('off')
    plt.savefig(buf, format='png')
    plt.close()
    print("Image saved to buffer.")  



def determine_image_path(node_type):
    image_paths = {
        'PC': 'images/desktop.png',
        'Switch': 'images/SwitchBlue.png',
        'Firewall': 'images/firewall.png',
        'Router': 'images/RouterBlue.png',
        'NAT': 'images/cloud-computing.png',
        'Hub': 'images/HubBlue.png',
        'Cloud': 'images/cloud-computing.png',
        'FRSW': 'images/FRSW.png'
    }
    return image_paths.get(node_type, 'images/RouterBlue.png')  



def determine_icon_size(node_type):
    sizes = {
        'PC': 0.060,  
        'Switch': 0.080,  
        'Firewall': 0.080,  
        'Router': 0.073,  
        'NAT': 0.080,  
        'Hub': 0.080,  
        'Cloud': 0.080, 
        'FRSW': 0.105  
    }
    return sizes.get(node_type, 0.05)  

def determine_font_attributes(node_type):
    attributes = {
        'PC': (8, 'bold', 'blue'),
        'Switch': (8, 'bold', 'white'),
        'Firewall': (8, 'bold', 'white'),
        'Router': (10, 'bold', 'white'),
        'NAT': (10, 'bold', 'blue'),
        'Hub': (8, 'bold', 'white'),
        'Cloud': (10, 'bold', 'gray'),
        'FRSW': (7, 'bold', 'orange')
    }
    return attributes.get(node_type, (10, 'normal', 'black'))