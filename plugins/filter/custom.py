#!/usr/bin/env python

from ansible.utils.display import Display
from ansible.template import AnsibleUndefined
from io import BytesIO

display = Display()


# Create an aggregation on aggkeys (which may be a nested key) within the dictarr array of dicts.  Differs from the builtin jinja2 filter 'groupby' in that it returns a dict for each aggregation, rather than putting it at array elem 0.
def dict_agg(dictarr, aggkeys):
    results = {}

    if dictarr:
        for dictItem in dictarr:
            newDictItem = dictItem
            for aggkey in aggkeys.split('.'):
                if aggkey in newDictItem:
                    newDictItem = newDictItem[aggkey]
                else:
                    newDictItem = None
                    break
            if newDictItem:
                if newDictItem not in results:
                    results[newDictItem] = []

                results[newDictItem].append(dictItem)
    return results


# Return extra_vars string (i.e. what the command line expects for 'extra' vars) from a dict of extra variables
def extravars_from_dict(extravars_dict):
    import json
    if type(extravars_dict) is dict:
        return " ".join(["-e " + k + "='" + json.dumps(v, separators=(',', ':')) + "'" for k, v in extravars_dict.items()])
    else:
        if type(extravars_dict) != AnsibleUndefined:
            display.warning(u"extravars_from_dict - WARNING: could not parse extravars (%s) as dict" % str(extravars_dict))
        return ""


# Return the ASCII character for a given ordinal character code
def tochr(i):
    return chr(i)


# Query an XML string for specific elements
def xpath(xmlstr, xpath, namespaces=None):
    from ansible import errors
    try:
        from lxml import etree
    except ImportError:
        raise errors.AnsibleFilterError("Error: The `lxml` module is required")

    if not xpath:
        raise errors.AnsibleFilterError("Error: xpath not defined")

    if not xmlstr.strip():
        display.warning(u"xmlstr is empty")
        return []
    else:
        try:
            xml = etree.parse(BytesIO(xmlstr.encode('utf-8')), etree.XMLParser(remove_blank_text=False))
        except Exception as e:
            raise errors.AnsibleFilterError(f"Invalid XML input: {e}")

        ## If this is an array of strings (if the user has parsed out the final leaf node), then return the string; otherwise return the xml.tostring() value (ansible cannot use the native etree Element type anyway)
        xpath_res = xml.xpath(xpath, namespaces=namespaces, smart_strings=False)
        return [xpath_elem if type(xpath_elem) is str else etree.tostring(xpath_elem).decode() for xpath_elem in xpath_res]



class FilterModule(object):
    def filters(self):
        return {
            'dict_agg': dict_agg,
            'extravars_from_dict': extravars_from_dict,
            'xpath': xpath,
            'tochr': tochr
        }
