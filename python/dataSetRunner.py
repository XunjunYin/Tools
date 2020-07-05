# coding: utf-8
import yaml
import json
import requests
import jsonpath

# http://nodeca.github.io/js-yaml/
# https://goessner.net/articles/JsonPath/


yaml_config = """
# todo:
# * support post method if requests has notnull data
# * supports string type parameters, e.g.:
#   content: 12341,12342,12343,12344,12345,12346,12347,12348,12349,12340
# * supports counter type parameters, e.g.:
#   range: 0, 10, 1
# * support regex response parser, e.g.:
#   response_type: reg
#   names: a, b, c
#   pattern: a(\d+)b(\d+)c1(\w+)000

parameters:
-
  names:
  - vid
  - title
  filename: /tmp/test
  delimiter: ','

requests:
-
  headers:
    Cookie: xxxxx
  url: https://domain.com/video/articles/global/search?docid=${vid}
  names:
  -
    name: category
    path: $..history[?(@.userid == "system")].category
  -
    name: keywords
    path: $..history[?(@.userid == "system")].keywords
  -
    name: interests
    path: $..history[?(@.userid == "system")].interests

output: ${vid}, ${title}, ${category}, ${keywords}, ${interests}
"""


def http_json(path, data, headers):
    try:
        return json.loads(http_get(path, data, headers))
    except Exception, e:
        print "http_get failed for the path=%s, error=%s" % (path, e)
        return json.loads('{}')


def http_get(path, headers, timeout=30):
    res = requests.get(path, headers=headers, timeout=timeout)
    return res.content


def http_post(path, data, headers, timeout=30):
    res = requests.post(path, json.dumps(data), headers=headers, timeout=timeout)
    return res.content


def run():
    params = {}
    data = yaml.load(yaml_config, Loader=yaml.FullLoader)
    print type(data)
    print data

run()
