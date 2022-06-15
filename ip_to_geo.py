import argparse
import concurrent
import copy
import json
import socket
from concurrent.futures import ThreadPoolExecutor

import geolite2
import requests


def ip_to_geo_using_keycdn(ip):
    url = "https://tools.keycdn.com/geo.json?host={host}"
    headers = {
        'User-Agent': 'keycdn-tools:https://{host}'.format(host=ip)
    }
    geo_info = requests.get(url.format(host=ip), headers=headers).json()
    if 'status' in geo_info.keys():
        if geo_info['status'] == 'success':
            return geo_info['data']['geo']


def ip_to_geo_using_freegeoip(ip):
    url = "https://freegeoip.app/json/{host}".format(host=ip)
    headers = {
        "Content-Type": "application/json"
    }
    geo_info = requests.get(url, headers=headers).json()
    if geo_info['message']:
        geo_info['message'] = f'FreeGeoIP {geo_info["message"]}'
    return geo_info


def ip_to_geo_using_geolite2(ip, lang='en'):
    supported_langs = ['de', 'en', 'es', 'fr', 'ja', 'pt-BR', 'ru', 'zh-CN', '*']
    if type(lang) != list:
        lang = [lang]
    if not all(item in supported_langs for item in lang):
        return {'error': f'unsupported lang: {lang}'}
    reader = geolite2.geolite2.reader()
    data = reader.get(ip)
    metadata = {}
    if data:
        if data.get('subdivisions'):
            data['subdivisions'] = data['subdivisions'].pop()
        metadata = copy.deepcopy(data)
        if not '*' in lang:
            for k, v in data.items():
                if type(v) is dict:
                    # print(f'k: {k}, v: {v}')
                    for k1, v1 in v.items():
                        if k1 == 'names':
                            if type(v1) is dict:
                                # print(f'k1: {k1}, v1: {v1}')
                                for k2, v2 in v1.items():
                                    # print(f'k2: {k2}, v2: {v2}')
                                    if k2 not in lang:
                                        # print(f'remove {k2} {geo3[k][k1][k2]}')
                                        metadata[k][k1].pop(k2)
        return metadata


def ip_to_geo_using_hackertargetapi(ip):
    url = "https://api.hackertarget.com/geoip/?q={host}".format(host=ip)
    resp = requests.get(url)
    raw_data = resp.text.split('\n')
    geo_info = {}
    if len(raw_data) > 1:
        for raw_datum in raw_data:
            meta_data = raw_datum.split(':')
            geo_info[meta_data[0]] = meta_data[1]
        return geo_info
    return {f'message': f'hackertarget {"".join(raw_data)}'}


def engine(host, lang='en'):
    try:
        ip = socket.gethostbyname(host)
    except:
        print('\n' + '-' * 20)
        print(f'Host: {host}\nIP: socket error: cannot resolve hostname [{host}]')
        print('-' * 20)
        print()
        return
    print('\n' + '-' * 20)
    print(f'Host: {host}\nIP: {ip}')
    print('-' * 20)
    print()

    futures = []
    results = []
    with ThreadPoolExecutor() as executor:
        futures.append(executor.submit(ip_to_geo_using_freegeoip, ip))
        futures.append(executor.submit(ip_to_geo_using_keycdn, ip))
        futures.append(executor.submit(ip_to_geo_using_geolite2, ip, lang))
        futures.append(executor.submit(ip_to_geo_using_hackertargetapi, ip))
    for future in concurrent.futures.as_completed(futures):
        results.append(future.result())
    return results


parser = argparse.ArgumentParser(description='Get IP Geolocation Info')
group = parser.add_mutually_exclusive_group(required=True)
group.add_argument('-i', '--hostname', action='store',
                   metavar="<Hostname| IP Address>", dest='hostname')
group.add_argument('-f', '--filename', metavar='files that contains IP Addresses or Domains.',
                   action='store', dest='filename')
parser.add_argument('-l', '--language', metavar='<Language for GeoLite2 API>',
                    action='store', dest='language')
args = parser.parse_args()

host_list = []
lang = 'en'

if args.hostname:
    host = args.hostname
    if host.find(','):
        host_list.extend(host.split(','))
    else:
        host_list.append(host)

if args.filename:
    file = args.filename
    with open(file, 'r') as fp:
        host = fp.readline()
        while host:
            host = host.rstrip('\n').rstrip(' ')
            host_list.append(host)
            host = fp.readline()

if args.language:
    lang = args.language.rstrip('\n').rstrip(' ')
    if lang.find(','):
        lang = lang.split(',')

for host in host_list:
    results = engine(host=host, lang=lang)
    if results:
        for result in results:
            print(json.dumps(result, indent=4))
