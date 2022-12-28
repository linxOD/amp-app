import glob
import os

import lxml.etree as ET
from typesense import Client
from typesense.api_call import ObjectNotFound
from acdh_tei_pyutils.tei import TeiReader
from tqdm import tqdm

client = Client({
    'nodes': [{
        'host': '0.0.0.0', # For Typesense Cloud use xxx.a1.typesense.net
        'port': '8108',      # For Typesense Cloud use 443
        'protocol': 'http'   # For Typesense Cloud use https
    }],
    'api_key': 'xyz',
    'connection_timeout_seconds': 2
})

files = glob.glob('./data/editions/*/*.xml')

try:
    client.collections['amp'].delete()
except ObjectNotFound:
    pass

current_schema = {
    'name': 'amp',
    'fields': [
        {
            'name': 'id',
            'type': 'string'
        },
        {
            'name': 'rec_id',
            'type': 'string'
        },
        {
            'name': 'title',
            'type': 'string'
        },
        {
            'name': 'full_text',
            'type': 'string'
        },
        {
            'name': 'year',
            'type': 'int32',
            'optional': True,
            'facet': True,
        },
        {
            'name': 'persons',
            'type': 'string[]',
            'facet': True,
            'optional': True
        },
        {
            'name': 'places',
            'type': 'string[]',
            'facet': True,
            'optional': True
        },
        {
            'name': 'orgs',
            'type': 'string[]',
            'facet': True,
            'optional': True
        },
        {
            'name': 'works',
            'type': 'string[]',
            'facet': True,
            'optional': True
        }
    ]
}

client.collections.create(current_schema)

def get_entities(ent_type, ent_node, ent_name):
    entities = []
    for p in body:
        e_path = f'.//tei:rs[@type="{ent_type}"]/@ref'
        ent = p.xpath(e_path, namespaces={'tei': "http://www.tei-c.org/ns/1.0"})
        if len(ent) > 0:
            for r in ent:
                i = r.replace('#', '')
                p_path = f'.//tei:{ent_node}[@xml:id="{i}"]/tei:{ent_name}[1]//text()'
                entity = " ".join(" ".join(doc.any_xpath(p_path)).split())
                entities.append(entity)
    entities = set(entities)
    ent = []
    for x in entities:
        ent.append(x)
    return ent

records = []
for x in tqdm(files, total=len(files)):
    doc = TeiReader(xml=x,xsl='./xslt/preprocess_typesense.xsl')
    facs = doc.any_xpath('.//tei:body/tei:div/tei:pb/@facs')
    pages = 0
    for p in facs:
        p_group = f".//tei:body/tei:div/tei:p[preceding-sibling::tei:pb[1]/@facs='{p}']|.//tei:body/tei:div/tei:lg[preceding-sibling::tei:pb[1]/@facs='{p}']"
        body = doc.any_xpath(p_group)
        pages += 1
        record = {}
        record['id'] = os.path.split(x)[-1].replace('.xml', f".html?page={str(pages)}")
        record['rec_id'] = os.path.split(x)[-1]
        r_title = " ".join(" ".join(doc.any_xpath('.//tei:titleStmt/tei:title[@level="a"]/text()')).split())
        record['title'] = f"{r_title} Page {str(pages)}"
        try:
            date_str = doc.any_xpath('//tei:origin/tei:origDate/@notBefore')[0]
        except IndexError:
            date_str = "1000"
        try:
            record['year'] = int(date_str[:4])
        except ValueError:
            pass

        if len(body) > 0:
            # get unique persons per page
            ent_type = "person"
            ent_name = "persName"
            record['persons'] = get_entities(ent_type=ent_type, ent_node=ent_type, ent_name=ent_name)
            # get unique places per page
            ent_type = "place"
            ent_name = "placeName"
            record['places'] = get_entities(ent_type=ent_type, ent_node=ent_type, ent_name=ent_name)
            # get unique orgs per page
            ent_type = "org"
            ent_name = "orgName"
            record['orgs'] = get_entities(ent_type=ent_type, ent_node=ent_type, ent_name=ent_name)
            # get unique bibls per page
            ent_type = "lit_work"
            ent_name = "title"
            ent_node = "bibl"
            record['works'] = get_entities(ent_type=ent_type, ent_node=ent_node, ent_name=ent_name)
            record['full_text'] = ""
            for p in body:
                l = " ".join(''.join(p.itertext()).split())
                record['full_text'] += f" {l}"
            if len(record['full_text']) > 0:
                records.append(record)

make_index = client.collections['amp'].documents.import_(records)
print(make_index)
print('done with indexing amp')
