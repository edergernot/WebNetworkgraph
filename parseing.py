

def addtodata(key,output,hostname,vrf):
    global Data
    if key not in Data.keys():
        Data[key]=[]
    for line in output:
        item = {}
        item['Devicename']=hostname
        if vrf != "default":
            item["vrf"]=vrf
        for k in line.keys():
            item[k]=line[k]
        Data[key].append(item)



def parse_NTC(file, Data):
    from ntc_templates.parse import parse_output
    platform="cisco_ios"
    vrf='default'
    '''Using Parser from NTC'''
    print (f'parsing {file}') 
    with open (f"input_files/{file}") as f:
        filedata = f.read()
    hostname = file[:-12]
    filedata = filedata.split("****************************************")
    for command in filedata:
        if command == "": #ignore empty
            continue
        rawcommand=command.split("**----------------------------------------**")[0].strip()
        print (rawcommand)
        try:
            commandoutput=command.split("**----------------------------------------**")[1]
        except IndexError:
            print(f"Error in command: {command}")    
            continue     
        if "show version" in rawcommand:
            if "Cisco Nexus Operating System" in commandoutput:
                platform = "cisco_nxos"
            if "Cisco Adaptive Security Appliance" in commandoutput:
                platform = "cisco_asa"
        if "show system info" in rawcommand:
            platform="paloalto_panos"
        if "display version" in rawcommand:
            platform = "hp_comware"
        try:    
            parsed_output = parse_output(platform=platform, command=rawcommand, data=commandoutput)
        except TypeError:
            print (f"Error in Parsing: {rawcommand} on platform: {platform}")
            continue
        key = platform+"_"+rawcommand.replace(" ","_")
        addtodata(key,parsed_output,hostname,vrf)
        
        
        


def parse_PyATS(file):
    '''Using PyATS for Parsing'''
    print (f'parsinf {file}')