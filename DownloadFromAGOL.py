#!/usr/bin/python

import arcgis
import datetime
import shutil, re, os
import arcpy
import time
import csv

import time
import datetime
import requests
import sys
from urllib.parse import quote
import json
from array import array
import pathlib
import copy
import os
import shutil
import datetime
import csv
import yaml

def run(p, s):
    print('--------------------------', flush=True)
    print(f'Download From {p}', flush=True)
    print('--------------------------', flush=True)
    date_str = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
    csv_path = s['BACKUP_LOCATIONS']['GROUP_CSV']
    
    group_list = readGroupSheet(csv_path, p)
    if group_list is None: return None
    
    # make gis object to read group items
    gis, yose_username, yose_password = makeGIS(p, s[f'{p}_SOURCE'], s['SSL_CERT'])
    if gis is None: return None
    
    # get token
    print(' > getting token ...', end="")
    try:
        token = get_agol_token(s[f'{p}_SOURCE']['TOKEN_URL'], 
                               yose_username, 
                               yose_password, 
                               s[f'{p}_SOURCE']['REFERER'])
        print(' done', flush=True)
        
    except Exception as e:
        print(f'error: {e}', flush=True)
        return None
    
    if token is None: return None
        
    # iterate through groups
    for group in group_list:
        
        print(f' > {group[0]} ...', end='')
        
        group_id = group[1]
        items = getItemsInGroup(group_id, gis)

        if items is None:
            continue
        
        if len(items) < 1:
            print(' has no items to download', flush=True)
            continue
            
        start_time = datetime.datetime.now().strftime("%H:%M:%S")
        print(f' started at {start_time}', flush=True)
            
        json_folder_path = getDownloadFolder(group, p, s['BACKUP_LOCATIONS']['DOWNLOAD_FOLDER'])
        print(json_folder_path)
        
        for i in items:
            print(f" \t - downloading {i.title} ...", end='')
            layer_ids = [str(url).split('/')[-1].split('"')[0] for url in i.layers]

            idResponse = request_ids(i.url, layer_ids, token)

            if idResponse is None:
                print(' -- error in extracting ids request', flush=True)
                continue

            idCount = sum([len(lyr['objectIds']) for lyr in idResponse['layers']])
            print('{} records'.format(str(idCount), end=''))

            if idCount < 0:
                print(' -- no records in this layer to download', flush=True)
                continue

            if idCount < 1000:
                requestResponse = request_extract(i.url, layer_ids, token, "1=1")

            else:
                # make multiple requests to get around 1000 max record return
                requestResponse = {'layers':[]}

                for lyr in idResponse['layers']:
                    layer_id = lyr['id']
                    id_list = lyr['objectIds']
                    lyrResponse = None

                    while id_list:
                        temp_list = id_list[:999]
                        id_list = id_list[999:]
                        lyr_query = "OBJECTID IN ({})".format(','.join([str(i) for i in temp_list]))
                        tempResponse = request_extract(i.url, layer_id, token, lyr_query)

                        if lyrResponse is None:
                            lyrResponse = tempResponse['layers'][0]

                        else:
                            new_feat = tempResponse['layers'][0]['features']
                            lyrResponse['features'].extend(new_feat)

                    requestResponse['layers'].append(lyrResponse)

            json_name = f"{removeSpecialCharacters(i.title)}.json"
            json_path = os.path.join(json_folder_path, json_name)

            with open(json_path, 'w') as json_file:
                json.dump(requestResponse, json_file)
                print(f'\t --> saved as {json_name}', flush=True)
                
                
        shutil.make_archive(json_folder_path, 
                            "zip", 
                            json_folder_path)
        shutil.rmtree(json_folder_path)

def removeSpecialCharacters(my_str):
    ''' removes characters that are not letters or numbers '''
    
    new_str = re.sub('[^A-Za-z0-9]+', '', my_str)
    return new_str

def parse_yaml(configFilePath):
    with open(configFilePath) as configFile:
        configText = configFile.read()

    configData = yaml.safe_load(''.join(configText))
    return configData

def makeGIS(p, p_source, sslCert):
    ''' GIS is arcgis python api object to interact with cloud '''
    
    gis_url = p_source['GIS_URL']
    yose_username = p_source['USERNAME']
    yose_password = p_source['PASSWORD']
    print(' > getting gis ...', end="")
    
    try:
        gis = arcgis.gis.GIS(gis_url, yose_username, yose_password, verify_cert=False)
        print(f' {p} connection established', flush=True)
        return gis, yose_username, yose_password
    
    except Exception as e:
        print('', flush=True)
        print(' -- error establishing gis connection. Cannot complete download.')
        print(e)
        return None

def readGroupSheet(group_csv, p):
    ''' returns a list of groups in the specified platfrm
        from the group download csv '''
    
    group_list = []

    with open(group_csv, newline='', encoding = 'utf-8') as csvread:
        reader = csv.reader(csvread, delimiter=',')
        headers = next(reader)
        readdict = csv.DictReader(csvread, delimiter=',', fieldnames = headers)
        for row in readdict:
            if row['PLATFORM'].lower() == p.lower():
                group_list.append((row['GROUPNAME'], row['GROUPID']))

    return group_list


def getItemsInGroup(grp_id, gis):
    ''' returns a list of items within a specified group on AGOL or portal '''
            
    try:
        items = [i for i in gis.groups.get(grp_id).content() if i.type == 'Feature Service']
        return items
    except AttributeError:
        print(f' group at {grp_id} does not exist', flush=True)
        return None

def getItemsInFolder(user, folder_name, gis):
    ''' returns a list of items within a user's folder on AGOL or portal '''
    
    for folder in user.folders:
        if folder['title'] == folder_name: break

    items = [i for i in user.items(folder) if i.type == 'Feature Service']
    return items


def get_agol_token(token_url, username, password, referer=''):
    ''' SSL certificate is on the web, verification is possible  '''
    payload = f'username={quote(username)}&password={quote(password)}&f=json&referer={quote(referer)}'
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded'
    }

    response = requests.request(
        "POST", token_url, headers=headers, data=payload, verify=False)
    responseBody = json.loads(response.text.encode('utf8'))

    if 'token' not in responseBody:
        print('', flush=True)
        print(f' -- Error generating token: {responseBody["error"]} --', flush=True)
        return None

    return responseBody['token']

def request_ids(feature_service_url, layer_ids, token):

    layer_queries = {}
    for layer_id in layer_ids:
        layer_queries[int(layer_id)] = "1=1"

    url = "{}/query?f=json&token={}".format(feature_service_url, token)
    data = "layerDefs={}&returnGeometry=false&returnIdsOnly=true".format(quote(json.dumps(layer_queries)))
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded'
    }

    response = requests.request("POST", url, headers=headers, data=data, verify=False)
    responseBody = json.loads(response.text.encode('utf8'))

    if 'error' not in responseBody.keys():
        return responseBody

    else:
        print('', flush=True)
        print(' \t -- error accessing the SOURCE feature service ids -- ', flush=True)
        for r in responseBody['error']:
            print(f"\t * {r}: {responseBody['error'][r]}", flush=True)
        return None

    return responseBody 

def request_extract(feature_service_url, layer_ids, token, lyr_query):

    layer_queries = {}
    if type(layer_ids) == list:
        for layer_id in layer_ids:
            layer_queries[int(layer_id)] = lyr_query

    else:
        layer_queries[layer_ids] = lyr_query

    url = "{}/query?f=json&token={}".format(feature_service_url, token)
    data = "layerDefs={}&returnGeometry=true".format(quote(json.dumps(layer_queries)))
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded'
    }

    response = requests.request("POST", url, headers=headers, data=data, verify=False)
    responseBody = json.loads(response.text.encode('utf8'))

    if 'error' not in responseBody.keys():
        return responseBody

    else:
        print('', flush=True)
        print(' \t -- error accessing the SOURCE feature service geometries and attributes -- ', flush=True)
        for r in responseBody['error']:
            print(f"\t * {r}: {responseBody['error'][r]}", flush=True)
        return None

    return responseBody                


def getDownloadFolder(group, p, download_folder):
    # establish group folder
    
    group_folder_name = removeSpecialCharacters(group[0])
    group_folder_path = os.path.join(download_folder, p, group_folder_name)

    if not os.path.isdir(group_folder_path):
        os.mkdir(group_folder_path)
        print(f' \t ! {group_folder_path} has been created - go set permissions')

    # establish today's json folder
    today = datetime.datetime.now().strftime("%Y%m%d_%H%M")
    json_folder_name = f"{p}_download_{today}"
    json_folder_path = os.path.join(group_folder_path, json_folder_name)
    
    if not os.path.isdir(json_folder_path):
        os.mkdir(json_folder_path)
        
    return json_folder_path

def main(configFilePath='settings_download_agol.yaml'):

    startTime = datetime.datetime.now()
    startTimeStr = startTime.strftime('%Y%m%d%H%M%S')

    configData = parse_yaml(configFilePath)

    if not os.path.isdir(configData['BACKUP_LOCATIONS']['LOG_FOLDER']):
        print(f"{configData['BACKUP_LOCATIONS']['LOG_FOLDER']} does not exist")
        return None

    thisLog = os.path.join(configData['BACKUP_LOCATIONS']['LOG_FOLDER'], f"downloadFromCloud_{startTimeStr}.log")

##    sys.stdout = open(thisLog, 'a')
##    sys.stderr = open(thisLog, 'a')

    print(f'**  start time: {startTime.strftime("%d/%m/%Y %H:%M:%S")}  **', flush=True)

    agol_results = run('AGOL', configData)
    portal_results = run('PORTAL', configData)

    print('---------------------------------------------------------------------------------------------------------', flush=True)
    print('''files have been stored as JSON. To extract the Feature Services to Feature Classes use the tool
          in YOSE CUSTOM TOOLS''', flush=True)
    print('---------------------------------------------------------------------------------------------------------', flush=True)
    

    endTime = datetime.datetime.now()
    print(f'**  end time: {endTime.strftime("%H:%M:%S")}  **', flush=True)
    runTime = endTime - startTime
    print(f'run time: {runTime}', flush=True)

if __name__ == '__main__':

    configFilePath = r'\\inpyosegis\Admin\Tools\AutomatedScripts\agol_portal_settings.yaml'

    if os.path.exists(configFilePath):
        main(configFilePath)

    else:
        print(' -- configuration file does not exist --', flush=True)
            
