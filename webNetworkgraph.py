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

############## Logging Level #################
#logging.basicConfig(level=logging.DEBUG)
logging.basicConfig(level=logging.ERROR)
##############################################

UPLOAD_FOLDER = './input_files'
ALLOWED_EXTENSIONS = {'zip'}
OUTPUT_FOLDER = './output_files'
RUNNING = f'{OUTPUT_FOLDER}/running'
data ={}  # Dict with all parsed Data


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
    #if "parsed_data.json" in files:
    #    with open (f"{UPLOAD_FOLDER}/parsed_data.json") as f:
    #        data = json.load(f)
    #else:
    if True:  ### WOrkarround to do allways a fresh Parse
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
