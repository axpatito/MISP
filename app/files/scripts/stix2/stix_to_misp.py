# -*- coding: utf-8 -*-
#    Copyright (C) 2017-2018 CIRCL Computer Incident Response Center Luxembourg (smile gie)
#    Copyright (C) 2017-2018 Christian Studer
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.

import sys, json, os, time
import stix2
# from stix2 import *
import pymisp

class StixParser():
    def __init__(self):
        self.misp_event = pymisp.MISPEvent()
        self.event = []

    def loadEvent(self, args, pathname):
        # try:
        filename = os.path.join(pathname, args[1])
        tempFile = open(filename, 'r')
        self.filename = filename
        event = stix2.get_dict(tempFile)
        for o in event.get('objects'):
            try:
                self.event.append(stix2.parse(o))
            except:
                self.parse_custom(o)
        # except:
        #     print(json.dumps({'success': 0, 'message': 'The temporary STIX export file could not be read'}))
        #     sys.exit(1)

    def parse_custom(self, obj):
        custom_object_type = obj.pop('type')
        labels = obj['labels']
        try:
            @stix2.CustomObject(custom_object_type,[('id', stix2.properties.StringProperty(required=True)),
            ('x_misp_timestamp', stix2.properties.StringProperty(required=True)),
            ('labels', stix2.properties.ListProperty(labels, required=True)),
            ('x_misp_value', stix2.properties.StringProperty(required=True)),
            ('created_by_ref', stix2.properties.StringProperty(required=True)),
            ('x_misp_comment', stix2.properties.StringProperty()),
            ('x_misp_category', stix2.properties.StringProperty())
            ])
            class Custom(object):
                def __init__(self, **kwargs):
                    return
        except:
            @stix2.CustomObject(custom_object_type,[('id', stix2.properties.StringProperty(required=True)),
            ('x_misp_timestamp', stix2.properties.StringProperty(required=True)),
            ('labels', stix2.properties.ListProperty(labels, required=True)),
            ('x_misp_values', stix2.properties.DictionaryProperty(required=True)),
            ('created_by_ref', stix2.properties.StringProperty(required=True)),
            ('x_misp_comment', stix2.properties.StringProperty()),
            ('x_misp_category', stix2.properties.StringProperty())
            ])
            class Custom(object):
                def __init__(self, **kwargs):
                    return
        custom = Custom(**obj)
        self.event.append(stix2.parse(custom))

    def handler(self):
        self.outputname = '{}.stix2'.format(self.filename)
        if self.from_misp():
            self.buildMispDict()
        else:
            self.buildExternalDict()

    def from_misp(self):
        for o in self.event:
            if o._type == 'report' and 'misp:tool="misp2stix"' in o.get('labels'):
                index = self.event.index(o)
                self.report = self.event.pop(index)
                return True
        return False

    def buildMispDict(self):
        self.parse_identity()
        self.parse_report()
        for o in self.event:
            object_type = o._type
            labels = o.get('labels')
            if object_type in ('observed-data', 'indicator'):
                if 'from_object' in labels:
                    self.parse_object(o, labels)
                else:
                    self.parse_attribute(o, labels)

    def parse_identity(self):
        identity = self.event.pop(0)
        org = {'name': identity.get('name')}
        self.misp_event['Org'] = org

    def parse_report(self):
        report = self.report
        self.misp_event.info = report.get('name')
        if report.get('published'):
            self.misp_event.publish_timestamp = self.getTimestampfromDate(report.get('published'))
        if report['labels']:
            labels = report['labels']
            for l in labels:
                self.misp_event.add_tag(l)
        if report['external_references']:
            ext_refs = report['external_references']
            for e in ext_refs:
                link = {"type": "link"}
                comment = e.get('source_name').split('url - ')[1]
                if comment:
                    link['comment'] = comment
                link['value'] = e.get('url')
                self.misp_event.add_attribute(**link)

    def parse_object(self, o, labels):
        object_type = o.get('type')

    def parse_attribute(self, o, labels):
        attribute_type = self.get_misp_type(labels)
        attribute_category = self.get_misp_category(labels)
        attribute = {'type': attribute_type, 'category': attribute_category}
        stix_type = o._type
        if stix_type == 'indicator':
            o_date = o.get('valid_from')
            pattern = o.get('pattern')
            value = self.resolve_pattern(pattern)
        else:
            o_date = o.get('first_observed')
            observable = o.get('objects')
            self.resolve_observable(observable)
        attribute['timestamp'] = self.getTimestampfromDate(o_date)
        try:
            attribute['value'] = value
            self.misp_event.add_attribute(**attribute)
        except:
            pass

    def buildExternalDict(self):
        sys.exit(1)
        for o in self.event:
            print(o)

    def saveFile(self):
        eventDict = self.misp_event.to_json()
        print(eventDict)

    @staticmethod
    def getTimestampfromDate(stix_date):
        return int(stix_date.timestamp())

    @staticmethod
    def get_misp_type(labels):
        return labels[0].split('=')[1][1:-1]

    @staticmethod
    def get_misp_category(labels):
        return labels[1].split('=')[1][1:-1]

    @staticmethod
    def resolve_pattern(pattern):
        if ' AND ' in pattern:
            pattern_parts = pattern.split(' AND ')
            if len(pattern_parts) == 3:
                _, value1 = pattern_parts[2].split(' = ')
                _, value2 = pattern_parts[0].split(' = ')
            else:
                _, value1 = pattern_parts[0].split(' = ')
                _, value2 = pattern_parts[1].split(' = ')
            return '{}|{}'.split(value1[1:-1], value2[1:-1])
        else:
            return pattern.split(' = ')[1][1:-1]

    @staticmethod
    def resolve_observable(observable):
        print(observable)

def main(args):
    pathname = os.path.dirname(args[0])
    stix_parser = StixParser()
    stix_parser.loadEvent(args, pathname)
    stix_parser.handler()
    stix_parser.saveFile()

if __name__ == "__main__":
    main(sys.argv)