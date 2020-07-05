# coding: utf-8
import yaml
import json
import requests

yaml_config = """
# todo:
# * supports string type parameters, e.g.:
#   content: 12341,12342,12343,12344,12345,12346,12347,12348,12349,12340
# * supports counter type parameters, e.g.:
#   range: 0, 10, 1
# * support regex response parser, e.g.:
#   response_type: reg
#   names: a, b, c
#   pattern: a(\d+)b(\d+)c1(\w+)000
# * support json fields multi-level parse
# * support post method if requests has notnull data

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
    Cookie: _ntes_nnid=7f4d8d9e5c7c4fac5e7f34d20111171b,1589865399736; _ga=GA1.2.889812554.1590738060; _zm_launcher=1590746052452; hb_MA-AF5D-8C93007541D1_source=lake.ws.netease.com; _antanalysis_s_id=1593314842768; _#cms_ar_admin_sid=cms_articlefilter_session_F6DD7391B0C29CD0DF5E81C3BE7B95C2A7EB0C59F29EF40178FE8E870A97877D; _#privilege_admin_sid=privilege_session_A7107D2E4C59BBC007A1949E7B8CA29AAFA42D9C34E249220AB6F05121885B63; op_state_id_1.0=704inzp0st; mp_MA-AF5D-8C93007541D1_hubble=%7B%22sessionReferrer%22%3A%20%22https%3A%2F%2Fmedia.youdata.netease.com%2Fdash%2Ffolder%2F450200678%3Frid%3D34504%22%2C%22updatedTime%22%3A%201593937522125%2C%22sessionStartTime%22%3A%201593936937030%2C%22sendNumClass%22%3A%20%7B%22allNum%22%3A%2050%2C%22errSendNum%22%3A%200%7D%2C%22deviceUdid%22%3A%20%228d8d5be1-c68f-4c96-909e-a4d37eb6c981%22%2C%22persistedTime%22%3A%201591148034611%2C%22LASTEVENT%22%3A%20%7B%22eventId%22%3A%20%22sql_query%22%2C%22time%22%3A%201593937522125%7D%2C%22currentReferrer%22%3A%20%22https%3A%2F%2Fmedia.youdata.netease.com%2Fdash%2Ffolder%2F450200678%3Frid%3D33275%26did%3D52447%22%2C%22sessionUuid%22%3A%20%22c467f848-4890-40c2-8071-c61a6fac9a11%22%2C%22user_id%22%3A%20%22xjyin%40corp.netease.com%22%2C%22costTime%22%3A%20%7B%7D%7D
  url: https://ar.ws.netease.com/video/articles/global/search?docid=${vid}
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
