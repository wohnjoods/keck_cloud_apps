import csv
import http
import requests
import json
subprocess.check_call([sys.executable, "-m", "pip", "install", "msal"])
import msal



def get_access_token(tenantID,clientID,clientSecret,dfcaID):
    authority = "https://login.microsoftonline.com/"+tenantID#+"/oauth2/token"
    scope = [dfcaID+'/.default']#['https://graph.microsoft.com/.default']
    app = msal.ConfidentialClientApplication(clientID, authority=authority, client_credential = clientSecret)
    access_token = app.acquire_token_for_client(scopes=scope)
    #acquire_token_for_client
    return access_token

tenantID = "" #REPLACE
clientID = "" #REPLACE
clientSecret = "" #REPLACE
tenant_name = "" #REPLACE
tenant_region = '' #REPLACE
dfcaID = '05a65629-4c1b-48c1-a78b-804c4abdd4af'
OPTION_DELETE_ENABLED = False
#tenant_id = 
COMBINE_ROWS = True #UPDATE
COMBINED_IP_RANGE_NAME = "Risky IP Import"#UPDATE
COMBINED_IP_RANGE_CATEGORY = "3"
COMBINED_IP_RANGE_TAG = ""
COMBINED_IP_ISP_NAME = ""
IP_RANGES_BASE_URL = 'https://'+tenant_name+'.'+tenant_region+'.portal.cloudappsecurity.com/api/v1/subnet/'
IP_RANGES_UPDATE_SUFFIX = 'update_rule/'
IP_RANGES_CREATE_SUFFIX = 'create_rule/'
CSV_ABSOLUTE_PATH = 'bad_ips.csv' #ENSURE CORRECT
access_token = get_access_token(tenantID,clientID,clientSecret,dfcaID)
YOUR_TOKEN = access_token['access_token']
#print(YOUR_TOKEN)

HEADERS = {
  'Authorization': 'Bearer {}'.format(YOUR_TOKEN),
  'Content-Type': 'application/json'
}
 
# Get all records.
def get_records():
  list_request_data = {
    # Optionally, edit to match your filters
    'filters': {},
    "skip": 0,
    "limit": 20
  }
  records = []
  has_next = True
  while has_next:
    response = requests.post(IP_RANGES_BASE_URL, json=list_request_data, headers=HEADERS)
    if response.status_code != http.HTTPStatus.OK:
      raise Exception(f'Error getting existing subnets from tenant. Stopping script run. Error: {response.content}')
    content = json.loads(response.content)
    response_data = content.get('data', [])
    records += response_data
    has_next = content.get('hasNext', False)
    list_request_data["skip"] += len(response_data)
  return records
 
# Rule fields are compared to the CSV row.
def rule_matching(record, ip_address_ranges, category, tag, isp_name, ):
  new_tags = sorted([new_tag for new_tag in tag.split(' ') if new_tag != ''])
  existing_tags = sorted([existing_tag.get('id') for existing_tag in record.get('tags', [])])
  rule_exists_conditions = [sorted([subnet.get('originalString', False) for subnet in record.get('subnets', [])]) !=
  sorted(ip_address_ranges.split(' ')),
  str(record.get('category', False)) != category,
  existing_tags != new_tags,
  bool(record.get('organization', False)) != bool(isp_name) or
  (record.get('organization', False) is not None and not isp_name)]
  if any(rule_exists_conditions):
    return False
  return True
 
def create_update_rule(name, ip_address_ranges, category, tag, isp_name, records, request_data):
  for record in records:
    # Records are compared by name(unique).
    # This can be changed to id (to update the name), it will include adding id to the CSV and changing row shape.
    if record["name"] == name:
    # request_data["_tid"] = record["_tid"]
      if not rule_matching(record, ip_address_ranges, category, tag, isp_name):
        # Update existing rule
        request_data['_id'] = record['_id']
        response = requests.post(f"{IP_RANGES_BASE_URL}{record['_id']}/{IP_RANGES_UPDATE_SUFFIX}", json=request_data, headers=HEADERS)
        if response.status_code == http.HTTPStatus.OK:
          print('Rule updated', request_data)
        else:
          print('Error updating rule. Request data:', request_data, ' Response:', response.content)
          json.loads(response.content)
        return record
      else:
        # The exact same rule exists. no need for change.
        print('The exact same rule exists. no need for change. Rule name: ', name)
        return record
  # Create new rule.
  response = requests.post(f"{IP_RANGES_BASE_URL}{IP_RANGES_CREATE_SUFFIX}", json=request_data, headers=HEADERS)
  if response.status_code == http.HTTPStatus.OK:
    print('Rule created:', request_data)
  else:
    print('Error creating rule. Request data:', request_data, ' Response:', response.content)
    # added record
    return record
 
# Request data creation.
def create_request_data(name, ip_address_ranges, category, tag, isp_name):
  tags = [new_tag for new_tag in tag.split(' ') if new_tag != '']
  request_data = {"name": name, "subnets": ip_address_ranges.split(' '), "category": category, "tags": tags}
  if isp_name:
    request_data["overrideOrganization"] = True
    request_data["organization"] = isp_name
  return request_data
 
def main():
  # CSV fields are: Name,IP_Address_Ranges,Category,Tag(id),Override_ISP_Name
  # Multiple values (eg: multiple subnets) will be space-separated. (eg: value1 value2)
  records = get_records()
  with open(CSV_ABSOLUTE_PATH, newline='\n') as your_file:
    reader = csv.reader(your_file, delimiter=',')
    # move the reader object to point on the next row, headers are not needed
    next(reader)
    if COMBINE_ROWS:
      all_ips = ""
      for row in reader:
        all_ips += str(row[1])
        all_ips += " "
      all_ips = all_ips.strip()
      reader = [[COMBINED_IP_RANGE_NAME,all_ips,COMBINED_IP_RANGE_CATEGORY,COMBINED_IP_RANGE_TAG,COMBINED_IP_ISP_NAME]]
      
      

    for row in reader:
      name, ip_address_ranges, category, tag, isp_name = row
      
      request_data = create_request_data(name, ip_address_ranges, category, tag, isp_name)
      if records:
      # Existing records were retrieved from your tenant
        record = create_update_rule(name, ip_address_ranges, category, tag, isp_name, records, request_data)
        print(record)
        record_id = record['_id']
      else:
        # No existing records were retrieved from your tenant
        response = requests.post(f"{IP_RANGES_BASE_URL}{IP_RANGES_CREATE_SUFFIX}", json=request_data, headers=HEADERS)
        if response.status_code == http.HTTPStatus.OK:
          record_id = json.loads(response.content)
          print('Rule created:', request_data)
        else:
          print('Error creating rule. Request data:', request_data, ' Response:', response.content)
      if OPTION_DELETE_ENABLED:
        # Remove CSV file record from tenant records.
        if record_id:
          for record in records:
            if record['_id'] == record_id:
              records.remove(record)
  if OPTION_DELETE_ENABLED:
    # Delete remaining tenant records, i.e. records that aren't in the CSV file.
    for record in records:
      requests.delete(f"{IP_RANGES_BASE_URL}{record['_id']}/", headers=HEADERS)
 
if __name__ == '__main__':
  main()