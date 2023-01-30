import arcpy
import datetime
import shutil, re, os
import csv
import sys
import json
import zipfile

def msg(txt):
    arcpy.AddMessage(txt)
    print(txt)

def modifyJSON(json_dict):
    layers = json_dict['layers']
    fc_list = []

    for lyr in layers:
        # remove global id field name information
        if 'globalIdFieldName' in list(lyr.keys()):
            del lyr['globalIdFieldName']
        
        # remove extraneous information about fields
        if 'fields' not in list(lyr.keys()):
            continue
        for field in lyr['fields']:
            del field['alias']
            del field['sqlType']
            try: del field['defaultValue']
            except: pass
            if field['domain'] is None: del field['domain']

            # save global ids as strings
            if field['name'].upper() == 'GLOBALID':
                field['type'] = 'esriFieldTypeString'
                

        fc_list.append(lyr)

    return fc_list

def putDomainsInGDB(json_name, temp_json, gdb):

    gdb_domains = [dom.name for dom in arcpy.da.ListDomains(gdb)]
    type_dict = {'esriFieldTypeString': 'TEXT',
                 'esriFieldTypeDouble': 'DOUBLE',
                 'esriFieldTypeInteger': 'LONG',
                 'esriFieldTypeSmallInteger': 'SHORT'}

    field_domains = {}

    ct = 0
    for lyr in temp_json['layers']:
        if 'fields' not in list(lyr.keys()): continue

        fc_name = f"{json_name.replace('.json', '')}_{ct}"
        ct += 1
        field_domains[fc_name] = {}
        
        fields = lyr['fields']
        for field in fields:
            if field['domain'] is None: continue

            domain = field['domain']
            dom_name = domain['name']

            try:
                if dom_name not in gdb_domains and domain['type'] == 'codedValue':
                    dom_codes = [cv['code'] for cv in domain['codedValues'] if type(cv['code']) == int or cv['code'].isdigit()]
                    dom_type = type_dict[field['type']]
                    arcpy.management.CreateDomain(gdb,dom_name,dom_name,dom_type,'CODED')

                    for cv in domain['codedValues']:
                        arcpy.management.AddCodedValueToDomain(gdb,dom_name,cv['code'],cv['name'])

                    gdb_domains.append(dom_name)

                if domain['type'] == 'codedValue':
                    field_domains[fc_name][field['name']] = dom_name

            except Exception as e:
                msg(f' !! Error adding {dom_name}')
                msg(e)
                msg(' !! moving on .... ')
                

    return field_domains
        
def main(json_zip, gdb):

    json_folder = '\\'.join(gdb.split('\\')[:-1])
    json_folder = os.path.join(json_folder, 'JSON_EXTRACTS')
    dom_dict = {}
    if not os.path.isdir(json_folder): os.mkdir(json_folder)

    for f in os.listdir(json_folder):
        os.remove(os.path.join(json_folder, f))
    
    msg(f" > json folder: {json_folder}")

    if not os.path.exists(json_zip):
        raise Exception('zip file does not exist')
        return None

    msg(' > unzipping json zip file ...')
    with zipfile.ZipFile(json_zip, 'r') as zipRef:
        zipRef.extractall(json_folder)

    msg(' > modifying json before importing ...')
    for json_file in [j for j in os.listdir(json_folder) if '_mod.json' not in j and '.json' in j]:
        json_path = os.path.join(json_folder, json_file)
        with open(json_path, 'r') as json_read:
            og_json = json.load(json_read)

        # add domains to gdb
        msg(f' > adding domains from {json_file} to gdb ...')
        dom_dict.update(putDomainsInGDB(json_file, og_json, gdb))

        mod_jsons = modifyJSON(og_json)

        for ct in range(0, len(mod_jsons)):
            mod_response = mod_jsons[ct]

            mod_json_path = os.path.join(json_folder, json_file.replace(".json", f"_{ct}_mod.json"))

            with open(mod_json_path, 'w') as json_write:
                json.dump(mod_response, json_write)

    msg(' > converting modified jsons into feature classes ...')
    for f in os.listdir(json_folder):
        
        if '_mod.json' not in f: continue
        json_path = os.path.join(json_folder, f)

        fc_name = f.replace(" ", "_").replace("_mod.json", '')
        fc_path = os.path.join(gdb, fc_name)

        if arcpy.Exists(fc_path):
            msg(f'\t - {fc_name} already exists, it is getting deleted and replaced')
            arcpy.management.Delete(fc_path)

        try:
            arcpy.conversion.JSONToFeatures(json_path, fc_path)
            msg(f'\t - fc created for {f}')

        except:
            msg(f'\t - unable to create fc for {f}')
            continue

        # add domains to feature class
        if fc_name in list(dom_dict.keys()):
            for field in dom_dict[fc_name]:
                try:
                    arcpy.management.AssignDomainToField(fc_path, field, dom_dict[fc_name][field])
                except:
                    msg(f' !! cannot add domain {dom_dict[fc_name][field]} to {field}')
                      


if __name__ == '__main__':
    json_zip = arcpy.GetParameterAsText(0)
    gdb = arcpy.GetParameterAsText(1)
    main(json_zip, gdb)

# create as a python toolbox tool in ArcGIS Pro
# first parameter is a File datatype, and should point to the zipped file
# second parameter is a Workspace (geodatabase) where the JSON should be extracted

        
    
