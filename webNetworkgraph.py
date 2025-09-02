import os
from flask import Flask, flash, request, redirect, url_for, render_template,send_file
from werkzeug.utils import secure_filename
import shutil
import json
import parse_files
import logging
import subprocess
import webbrowser
import pandas
import dump_diff
import requests
import time
from dotenv import load_dotenv

############## Logging Level #################
#logging.basicConfig(level=logging.DEBUG)
logging.basicConfig(level=logging.ERROR)
##############################################

UPLOAD_FOLDER = './input_files'
ALLOWED_EXTENSIONS = {'zip'}
OUTPUT_FOLDER = './output_files'
RUNNING = f'{OUTPUT_FOLDER}/running'
data ={}  # Dict with all parsed Data
mac_vendor={}

### Load API Key from .envcc
load_dotenv()
API_KEY = os.getenv("MAC_IOU_API_KEY")


### Used for do a diff
INPUT_FOLDER="./input_files"
INPUTFOLDER="./input_files"
DIFFFOLDER="./diff"
WORKDIRS=[]
DEVICES=[]
WORKFILES=[]
parsed1={}
parsed2={}


app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['INPUT_FOLDER'] = INPUT_FOLDER
app.secret_key = 'B1178997E6F728FA9AF2C087DE6DEA4A'  #used to avoid session highjacking

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_status():
    files = 0
    files = len([f for f in os.listdir(UPLOAD_FOLDER) if os.path.isfile(f"{UPLOAD_FOLDER}/{f}")])
    parsed_commands = len(data.keys())
    status={"files":files, "parsed_commands":parsed_commands}
    return status
    
def unzip_all_files():
    files = [f for f in os.listdir(UPLOAD_FOLDER) if f.split(".")[-1] == "zip"]
    for file in files:
        shutil.unpack_archive(f"{UPLOAD_FOLDER}/{file}", UPLOAD_FOLDER)
        os.remove(f"{UPLOAD_FOLDER}/{file}")

def get_mac_vendor(MAC):
    global mac_vendor
    IOU = MAC.replace(".","")[:6]
    #print(f"check MAC: {MAC} IOU: {IOU}")
    try:
        vendor=mac_vendor[IOU]
        return vendor
    except KeyError: 
        pass 
    if API_KEY == None:
        return("Not Resolved, No Api Key")
    if API_KEY == "":
        return("Not Resolved, No Api Key")
    URL = f"https://api.maclookup.app/v2/macs/{MAC}/company/name?apiKey={API_KEY}"
    response = requests.get(URL)
    while response.status_code == 429:  #wait a Second for the next requests
        time.sleep(1)
        print("sleeped 1 second")
        response = requests.get(URL)       
    if response.status_code == 200:
        mac_vendor[IOU]=response.text
        print(f"{IOU} : {response.text}")
        return (response.text)
    return("Not Resolved")

def add_to_data(key, parsed, hostname, vrf='NONE'):
    global data
    MAC_IOU_Check = False
    if "show_mac_addr" in key:
        MAC_IOU_Check=True
    if key not in data.keys():
        data[key]=[]
    for line in parsed:
        item={}
        item['Devicename']=hostname
        if vrf != 'NONE':
            item['vrf']=vrf
        for k in line.keys():
            item[k]=line[k]
        if MAC_IOU_Check:
            item["MAC-Vendor"]=get_mac_vendor(line["destination_address"])

        data[key].append(item)

def generate_interfaceconfig_dict(interface_config:str)->dict:
    # Generate a dict from interface configurations
    interface:dict = {}
    interface["speed"]="auto"
    interface["duplex"]="auto"
    interface["switchport_mode"]="Not configured!"
    for line in interface_config.split("\n"):
        if len(line)<=2:
            continue
        if line == "no switchport":
            interface["switchport_mode"]="routed"
        if "switchport mode" in line:
            interface["switchport_mode"]=line.split()[-1].strip()
            continue
        if "description" in line:
            interface["description"]=line.split("description")[1].strip()
            continue
        if "switchport access vlan" in line:
            interface["vlan"]=line.split("vlan")[1].strip()
            continue
        if "switchport voice vlan" in line:
            interface["voice-vlan"]=line.split("vlan")[1].strip()
            continue
        if "port-security maximum" in line:
            interface["max_port_security"]=line.split("port-security")[1].strip()
            continue
        if "storm-control broadcast" in line:
            interface["stormctl_broadcast"]=line.split("storm-control broadcast")[1].strip()
            continue
        if "storm-control multicast" in line:
            interface["stormctl_multicast"]=line.split("storm-control multicast")[1].strip()
            continue
        if "storm-control action" in line:
            interface["stormctl_action"]=line.split("storm-control action")[1].strip()
            continue
        if "access-session port-control auto" in line:
            interface["Dot1x"] = "Enabled"
            continue
        if "authentication port-control auto" in line:
            interface["Dot1x"] = "Enabled"
            continue
        if "mab" in line:
            interface["Mab"] = "Enabled"
            continue
        if "service-policy type" in line:
            interface["ServicePolicy"]=line.split("service-policy type")[1].strip()
            continue
        if "dot1x pae" in line:
            interface["Dot1x_Int_Type"]=line.split("dot1x pae")[1].strip()
            continue
        if "speed" in line:
            interface["speed"]=line.split("speed")[1].strip()
            continue
        if "duplex" in line:
            interface["duplex"]=line.split("duplex")[1].strip()
        if "channel-group" in line:
            interface["portchannel"]=line.split("channel-group")[1].strip()
        if "switchport trunk allowed vlan" in line:
            try:
                vlans=interface["trunk_vlans"]
                vlans_add=line.split("add")[1].strip()
                interface["trunk_vlans"]=vlans+vlans_add
                continue
            except KeyError:
                interface["trunk_vlans"]=line.split("switchport trunk allowed vlan")[1].strip()
                continue
        if "device-tracking attach-policy" in line:
            interface["device_tracking_policy"]=line.split("device-tracking attach-policy")[1].strip()
        if "spanning-tree" in line:
            try:
                stp_setting=interface["spanning-tree"]
                stp_additional_setting=line.split("spanning-tree")[1].strip()
                interface["spanning-tree"]=stp_setting+" | "+stp_additional_setting
                continue
            except KeyError:
                interface["spanning-tree"]=line.split("spanning-tree")[1].strip()
                continue
    return(interface)

def write_interface_cfg_excel(all_interfaces):
    import pandas as pd
    df = pd.DataFrame(all_interfaces)
    writer = pd.ExcelWriter(f'{UPLOAD_FOLDER}/interface_cfg.xlsx', engine='xlsxwriter')
        
    # Write the dataframe data to XlsxWriter. Turn off the default header and
    # index and skip one row to allow us to insert a user defined header.
    df.to_excel(writer, sheet_name='Sheet1', startrow=1, header=False, index=False)
    
    # Get the xlsxwriter workbook and worksheet objects.
    workbook = writer.book
    worksheet = writer.sheets['Sheet1']
    
    # Get the dimensions of the dataframe.
    (max_row, max_col) = df.shape
    
    # Create a list of column headers, to use in add_table().
    column_settings = [{'header': column} for column in df.columns]
    
    # Add the Excel table structure. Pandas will add the data.
    worksheet.add_table(0, 0, max_row, max_col - 1, {'columns': column_settings}, )
    
    # Make the columns wider for clarity.
    worksheet.set_column(0, max_col - 1, 15)
         
    # Close the Pandas Excel writer and output the Excel file.
    writer._save()
    
def get_cdp_nei(interface,host):
    global data
    cdps=data["cisco_ios--show_cdp_neighbors_detail"]
    for cdp in cdps:
        if cdp["Devicename"]==host:
            if cdp['local_port']==interface:
                return(cdp['destination_host'])
    return("")

def generate_interface_cfg_excel(configdata):
    all_interfaces=[]
    for device in configdata:
        interface_blobs=device['config'].split('!\ninterface')
        for intconfig in interface_blobs:
            interface_config_dict:dict={}
            interface_config_dict['host']=device['Devicename']
            if intconfig[:8]=="Building": 
                continue
            if intconfig[:5]==" Vlan":
                continue
            if intconfig[:4]==" App":
                continue
            interface_config_dict['interface']=intconfig.split("\n")[0].strip()
            gererated_int_cfg = generate_interfaceconfig_dict(intconfig)
            for key in gererated_int_cfg.keys():  
                interface_config_dict[key]=gererated_int_cfg[key]
            interface_config_dict["cdp"]=get_cdp_nei(interface_config_dict['interface'],interface_config_dict['host'])
            all_interfaces.append(interface_config_dict)
    write_interface_cfg_excel(all_interfaces)

@app.route("/")
def index():
    '''    Render Index Side '''
    content=get_status()
    return render_template("index.html",status=content)

@app.route("/about")
def about():
    '''Render About Page'''
    content=get_status()
    return render_template("about.html",status=content)

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    '''Select file for upload and upload it.
    Only *.zip files are supported, zp-file will extract and zip-file is deleted after extraction'''
    content=get_status()
    if request.method == 'POST':
        # check if the post request has the file part
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        file = request.files['file']
        # If the user does not select a file, the browser submits an
        # empty file without a filename.
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            content=get_status()
            #print (content)  # Debug
            unzip_all_files()
            if os.path.exists(f"{OUTPUT_FOLDER}"):  #delete Outputfolder if exist
                shutil.rmtree(f"{OUTPUT_FOLDER}", ignore_errors=False, onerror=None)
            path = os.path.join("./",f"{OUTPUT_FOLDER[2:]}")
            os.mkdir(path)
            if os.path.exists(f"{UPLOAD_FOLDER}/running"): #copy running configs
                shutil.copytree(f"{UPLOAD_FOLDER}/running", f"{OUTPUT_FOLDER}/running/")
            return redirect('/')
    return render_template("upload.html",status=content)

@app.route('/start_graph')
def start_graph():
    #kill running app
    process = subprocess.Popen(['python', 'graphs.py'])
    webbrowser.open('http://localhost:8050',1)
    content=get_status()
    return render_template("graph.html",status=content)
   
@app.route('/parse')
def parse():
    '''Parse the uploaded Network_Dumpfile with TextFSM-Parser if not allready in Dumpfile'''
    global data
    files = [f for f in os.listdir(UPLOAD_FOLDER) if os.path.isfile(f"{UPLOAD_FOLDER}/{f}")]
    NoFiles=len(files)
    #if "parsed_data.json" in files:
    #    with open (f"{UPLOAD_FOLDER}/parsed_data.json") as f:
    #        data = json.load(f)
    #else:
    if True:  ### Workarround to do allways a fresh Parse
        for file in files:
            if file[-12:] != '_command.txt': # Check if Raw output file
                continue
            print(f'Parsing File: {file}')
            hostname = file[:-12]
            filename = f"{UPLOAD_FOLDER}/{file}"
            platform = "cisco_ios"
            with open(filename) as f:
                f_data=f.read()
                f_data1 = f_data.split('\n****************************************\n')
                for blob in f_data1:
                    try:
                        blobsplit=blob.split('\n**----------------------------------------**\n')
                        command=blobsplit[0]
                        output=blobsplit[1]
                    except IndexError:
                        continue
                    if "show version" in command:
                        if "Cisco Nexus Operating System" in output:
                            platform = "cisco_nxos"
                        if "Cisco Adaptive Security Appliance" in output:
                            platform = "cisco_asa"
                    if "show system info" in command:
                        platform="paloalto_panos"
                    if "display version" in command:
                        platform = "hp_comware"
                    if ' vrf ' in command: 
                        parsed_vrf=parse_files.parse_textfsm(command.split(' vrf ')[0], output, platform)
                        vrf_name=command.split(' vrf ')[1]
                        command = command.split( 'vrf ')[0]
                        if command[-1] == " ":
                            command = command[:-1]
                        if parsed_vrf==("Error","Error"):
                            logging.debug(f'webnetworkdump.parsing. Parsing Error on : {hostname} for command: {command}')
                            continue
                        key=platform+'--'+command.replace(' ','_')
                        add_to_data(key, parsed_vrf, hostname, vrf_name)
                        continue
                    if command == "show running":  # generate show running-config blob in data
                        parsed=[]
                        key=platform+'--'+command.replace(' ','_')
                        running={'config':output}
                        parsed.append(running)
                        add_to_data(key, parsed, hostname)
                        continue  
                    else:        
                        parsed=parse_files.parse_textfsm(command, output, platform)
                        if parsed==("Error","Error"):
                            logging.debug(f'webnetworkdump.parsing. Parsing Error on : {hostname} for command: {command}')
                            continue
                        key=platform+'--'+command.replace(' ','_')
                        add_to_data(key, parsed, hostname)       
        
    
    with open (f'{UPLOAD_FOLDER}/parsed_data.json', 'w') as file: # write json file
        file.write(json.dumps(data, indent=4))
    # generate Topology.json for Graphite
    os.system("python generate_json.py")
    keys = data.keys()
    content=get_status()          
    return render_template("parse.html",status=content, keys=keys)

@app.route('/download')
def download():
    for k in data.keys():
        if data[k]== []:
            continue
        if k == "cisco_ios--show_running":
            generate_interface_cfg_excel(data[k])
        df = pandas.DataFrame(data[k])
        df.to_excel(f'{UPLOAD_FOLDER}/{k}.xlsx')
    shutil.make_archive(f"{OUTPUT_FOLDER}/NetworkDumpParsed", "zip", f"{UPLOAD_FOLDER}")
    path = f"{OUTPUT_FOLDER}/NetworkDumpParsed.zip"
    return send_file(path, as_attachment=True)

@app.route('/diff', methods=['GET', 'POST'])
def diff():
    '''Upload 2 files taken Networkdunp-Files and do a diff'''
    content=get_status()
    if request.method == 'POST':
        # check if the post request has the file part
        # print (request.files)
        if 'file1' not in request.files or 'file2' not in request.files:
            flash('File Missing!')
            return redirect(request.url)
        
        file1 = request.files['file1']
        file2 = request.files['file2']

        # If the user does not select a file, the browser submits an
        # empty file without a filename.
        if file1.filename == '' or file2.filename == '':
            flash('Missing File')
            return redirect(request.url)
        
        if file1 and allowed_file(file1.filename) and file2 and allowed_file(file2.filename):
            filename1 = secure_filename(file1.filename)
            filename2 = secure_filename(file2.filename)
            file1.save(os.path.join(app.config['INPUT_FOLDER'], filename1))
            file2.save(os.path.join(app.config['INPUT_FOLDER'], filename2))
            flash('Files successfully uploaded')

            dump_diff.readfiles()
            dump_diff.create_devices()
            dump_diff.parse_devices()
        content=get_status()
        return redirect('/diff_done')        
    return render_template("diff.html",status=content)

@app.route('/diff_done')
def diff_done():
    shutil.make_archive(f"{OUTPUT_FOLDER}/NetworkDumpDiff", "zip", f"{DIFFFOLDER}")
    path = f"{OUTPUT_FOLDER}/NetworkDumpDiff.zip"
    flash('Diff Done')
    return send_file(path, as_attachment=True)

@app.route('/files')
def files():
    '''All files in upload folder are displayed.
    No directories are dispalyed'''
    files = [f for f in os.listdir(UPLOAD_FOLDER) if os.path.isfile(f"{UPLOAD_FOLDER}/{f}")]
    content=get_status()
    return render_template('files.html', status=content, files=files)

@app.route('/delete')
def delete():
    '''delete directorys if old dumps exist and create new dirs'''
    global data
    data = {}
    if os.path.exists(f"{UPLOAD_FOLDER}"):
        shutil.rmtree(f"{UPLOAD_FOLDER}", ignore_errors=False, onerror=None)
    path = os.path.join("./",f"{UPLOAD_FOLDER[2:]}")
    os.mkdir(path)
    if os.path.exists(f"{OUTPUT_FOLDER}"):
        shutil.rmtree(f"{OUTPUT_FOLDER}", ignore_errors=False, onerror=None)
    path = os.path.join("./",f"{OUTPUT_FOLDER[2:]}")
    os.mkdir(path)
    if os.path.exists(f"{DIFFFOLDER}"):
        shutil.rmtree(f"{DIFFFOLDER}", ignore_errors=False, onerror=None)
    path = os.path.join("./",f"{DIFFFOLDER[2:]}")
    os.mkdir(path)
    existing_folders = [f for f in os.listdir() if os.path.isdir(f)]
    folderneedet = ['templates', 'static', '.venv', 'diff', 'input_files', 'output_files', 'images', '__pycache__', '.git', 'assets']
    for folder in existing_folders:
        if folder in folderneedet:
            continue
        shutil.rmtree(folder)
        print (f"Delete Folder: {folder}")
    print ('Cleanup successful\n')
    return redirect('/')


app.run(host='0.0.0.0', port=5100, debug=False)
