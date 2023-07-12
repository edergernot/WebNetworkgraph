'''Generates the default.json file which can be used in graphite container
See: https://github.com/netreplica/graphite/'''

import json
import jinja2
data = {}
with open ("input_files/parsed_data.json") as f:
    data=json.load(f)
cdpkey = 'cisco_ios--show_cdp_neighbors_detail'
cdpdata = data[cdpkey]

nodes = []
links = []


def short_portname(port):
    if "GigabitEthernet" in port:
        newport = port.replace("GigabitEthernet", "Gi")
    elif "FastEthernet" in port:
        newport = port.replace("FastEthernet", "Fa")
    elif "FortyGigabitEthernet" in port:
        newport = port.replace("FortyGigabitEthernet", "Fo")
    elif "HundredGigE" in port:
        newport = port.replace("HundredGigE", "Hu")
    elif "TenGigabitEthernet" in port:
        newport = port.replace("TenGigabitEthernet", "Te")
    elif "TwentyFiveGigE" in port:
        newport = port.replace("TwentyFiveGigE", "Twe")
    elif "TwoGigabitEthernet" in port:
        newport = port.replace("TwoGigabitEthernet", "Two")
    elif "FiveGigabitEthernet" in port:
        newport = port.replace("FiveGigabitEthernet", "Fi")
    elif "FourHundredGigE" in port:
        newport = port.replace("FourHundredGigE", "400G")
    elif "Ethernet" in port:
        newport = port.replace("Ethernet", "Eth")
    else:
        newport = port
    return (newport)


def removeduplicate_links():
    global links
    existing_links=[]
    for link in links:
        exists=False
        for existing in existing_links: # check if link is allready here in reverse direction
            if existing["to"] == link["from"]:
                if existing["remote_port"] == link["local_port"]:
                    exists=True
        if not exists:
            existing_links.append(link)
    links = existing_links
                    


for line in cdpdata:
    host_exists = False
    link_exist = False
    link = {}
    node = {}
    try:
        node["id"]=line['destination_host'].split(".")[0]   #remove domain if FQDN is destination host
    except KeyError:
        continue
    node["type"]=line["capabilities"].split(" ")[0]  # user first adverdised capability
    link["from"]=line['Devicename']
    link["to"]=line['destination_host'].split(".")[0]
    link["local_port"]=short_portname(line["local_port"])  
    link["remote_port"]=short_portname(line["remote_port"])
    links.append(link)
    for existing_node in nodes:
        if node["id"] == existing_node["id"]:
            host_exists = True
    if not host_exists:
        nodes.append(node)

removeduplicate_links()

with open ("topology.j2") as f:
    template = f.read()

j2template = jinja2.Template(template)
data = {'nodes':nodes,
        'links':links}

with open ("./input_files/topology.json","w") as topo:
    topo.write((j2template.render(data)))


    

