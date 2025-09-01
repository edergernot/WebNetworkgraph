# WebNetworkGraph
This is an extension for WebNetworkDump.<br>
Because of using PyATS for Diff it will nor run on Windows! Jou have to run it on WSL or Linux!

Here you can Upload networkdump.zip files which were created with webnetworkdump : see: https://github.com/edergernot/webnetworkdump1.1 

I tested with Cisco IOS, IOS-XE, NX-OS, HP-Comware and Paloalto Firewalls.



## Easystart with DockerContainer on local maschine!

- Get Container from Dockerhub
  - ```docker run -p 5100:5100 -p 8050:8050 edergernot/webnetworkgraph```

- Start analycing the networkdump.zip file: 
  - ```http://localhost:5100```

Just upload the zip-file, parse it, graph it and download the parsed files.

Note: For graphing it just uses CDP-Data from Cisco-IOS Devices. This will change soon


## Working with webnetworkdump

Index
![Index](images/Index.png)

Upload
![Upload](images/Upload.png)

View Files
![View Files](images/ViewFiles.png)

Parse
![Device View](images/Parse.png)

Graph: If it do not open in a new Browserwindow go to http://localhost:8050
![Graph](images/Graph.png)

Download
![Download](images/download.png)

Dumpfile
![Dumpfile](images/Filecontext.png)


## Diff 2 Dumpfiles:
Dumpfiles will parsed with PyATS and a diff of the parsed JSON - Data is done!

Select Diff 2 Files and Choose NetworkDump.zip Files, Upload Button will start diff-Process
![Diff](images/Diff.png)

Diff is running:
![Diff Running](images/Diff_Running.png)

Diff-File will automaticly download when finished:
![Diff Download](images/Diff_Downloads.png)

In Diff-Zipfile there is a Folder for every Device:
![Diff Files](images/Diff_files.png)

In every Device-Folder is the "diff.txt" file as well as a Folder with parsed JSON Data from uploaded Dump-File.
The diff.txt is in Linux diff style + - 
![Diff Edit](images/diff_edit.png)

Diff ignored counters for interfaces and age for CDP etc.

## Run direct on Host
Windows is not supported because of PyATS (Python Version < 3.12). You have to use WSL or Linux!<br>
Clone the Repo:

```git clone https://github.com/edergernot/WebNetworkgraph```

For getting VendorCodes with the Mac-Tables create a .env file where the API-Key for the Mac-Vendorcode-API ist stored, like this. <br>
You can get it here: https://maclookup.app/api-v2/documentation

```MAC_IOU_API_KEY=abcdefghijklmnopqrstuvwxyz0123456789```

Install the Requirements

```pip install -r requirements.txt```

Run the App:

```python3 webNetworkgraph.py```

Browse the Webinterface:
http://localhost:5100