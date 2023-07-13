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



############## Logging Level #################
#logging.basicConfig(level=logging.DEBUG)
logging.basicConfig(level=logging.ERROR)
##############################################

UPLOAD_FOLDER = './input_files'
ALLOWED_EXTENSIONS = {'zip'}
OUTPUT_FOLDER = './output_files'
RUNNING = f'{OUTPUT_FOLDER}/running'
data ={}  # Dict with all parsed Data

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

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

def add_to_data(key, parsed, hostname, vrf='NONE'):
    global data
    if key not in data.keys():
        data[key]=[]
    for line in parsed:
        item={}
        item['Devicename']=hostname
        if vrf != 'NONE':
            item['vrf']=vrf
        for k in line.keys():
            item[k]=line[k]
        data[key].append(item)

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
    if "parsed_data.json" in files:
        with open (f"{UPLOAD_FOLDER}/parsed_data.json") as f:
            data = json.load(f)
    else:
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

                    else:        
                        parsed=parse_files.parse_textfsm(command, output, platform)
                        if parsed==("Error","Error"):
                            logging.debug(f'webnetworkdump.parsing. Parsing Error on : {hostname} for command: {command}')
                            continue
                        key=platform+'--'+command.replace(' ','_')
                        add_to_data(key, parsed, hostname)       
        
    
    with open (f'{UPLOAD_FOLDER}/parsed_data.json', 'w') as file: # write json file
        file.write(json.dumps(data, indent=4))   
    keys = data.keys()
    content=get_status()            
    return render_template("parse.html",status=content, keys=keys)

@app.route('/download')
def download():
    for k in data.keys():
        if data[k]== []:
            continue
        df = pandas.DataFrame(data[k])
        df.to_excel(f'{UPLOAD_FOLDER}/{k}.xlsx')
    shutil.make_archive(f"{OUTPUT_FOLDER}/NetworkDumpParsed", "zip", f"{UPLOAD_FOLDER}")
    path = f"{OUTPUT_FOLDER}/NetworkDumpParsed.zip"
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
    return redirect('/')

app.run(host='0.0.0.0', port=5100)
