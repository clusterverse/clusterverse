#!/usr/bin/env python

from ansible.utils.display import Display
from ansible.template import AnsibleUndefined
from io import BytesIO

display = Display()


class FilterModule(object):
    def filters(self):
        return {
            'dict_agg': self.dict_agg,
            'extravars_from_dict': self.extravars_from_dict,
            'xpath': self.xpath,
            'tochr': self.tochr,
            'region_short': self.region_short,
        }

    # Create an aggregation on aggkeys (which may be a nested key) within the dictarr array of dicts.  Differs from the builtin jinja2 filter 'groupby' in that it returns a dict for each aggregation, rather than putting it at array elem 0.
    def dict_agg(self, dictarr, aggkeys):
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
    def extravars_from_dict(self, extravars_dict):
        import json
        if type(extravars_dict) is dict:
            return " ".join(["-e " + k + "='" + json.dumps(v, separators=(',', ':')) + "'" for k, v in extravars_dict.items()])
        else:
            if type(extravars_dict) != AnsibleUndefined:
                display.warning(u"extravars_from_dict - WARNING: could not parse extravars (%s) as dict" % str(extravars_dict))
            return ""


    # Query an XML string for specific elements
    def xpath(self, xmlstr, xpath, namespaces=None):
        from ansible import errors
        try:
            from lxml import etree
        except ImportError:
            raise errors.AnsibleFilterError("Error: The `lxml` module is required")

        if not xpath:
            raise errors.AnsibleFilterError("Error: xpath not defined")

        # virt_volume get_xml returns {'Error': '...'} when the volume is missing; Ansible 2.21 wraps that as a lazy dict.
        if xmlstr is None or not isinstance(xmlstr, str):
            err = None
            if isinstance(xmlstr, dict):
                err = xmlstr.get('Error') or xmlstr
            raise errors.AnsibleFilterError("xpath expects an XML string, got %s%s" % ( type(xmlstr).__name__, (": %s" % err) if err else ""))

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


    # Return the ASCII character for a given ordinal character code
    def tochr(self, i):
        return chr(i)

    # Shorten a cloud region name for use in hostnames.
    def region_short(self, region):
        import re

        if region is None or isinstance(region, AnsibleUndefined):
            return ''

        region = str(region).strip().lower()
        if not region:
            return ''

        # Compass tokens (longest first so 'southeast' wins over 'south'/'east')
        compass = ('northeast', 'northwest', 'southeast', 'southwest', 'north', 'south', 'east', 'west', 'central')

        def geo_token(token):
            """First 2 chars of a geography token (europe->eu, us->us)."""
            return token[:2] if len(token) >= 2 else token

        def compass_abbrev(token):
            """north->n, southeast->se, etc. Returns None if not a compass word."""
            for name in compass:
                if token == name or token.startswith(name):
                    # token may be 'west4' (GCP); only consume the compass word
                    if token == name or token[len(name):].isdigit() or (
                        len(token) > len(name) and token[len(name)].isdigit()
                    ):
                        # multi-word compass: take first letter of each half if compound
                        if name in ('northeast', 'northwest', 'southeast', 'southwest'):
                            return name[0] + name[5]  # n+e, n+w, s+e, s+w
                        return name[0]
            return None

        def trailing_number(token):
            m = re.search(r'(\d+)$', token)
            return m.group(1) if m else ''

        # --- Hyphenated forms (AWS / GCP): eu-west-1, europe-west4, ap-southeast-1 ---
        if '-' in region:
            parts = region.split('-')
            out = []
            # First segment is geography
            out.append(geo_token(parts[0]))
            # Remaining segments: compass and/or number
            for part in parts[1:]:
                if part.isdigit():
                    out.append(part)
                    continue
                ca = compass_abbrev(part)
                if ca is not None:
                    out.append(ca)
                    num = trailing_number(part)
                    if num:
                        out.append(num)
                else:
                    # Unknown middle token: keep first letter (or digit run)
                    num = trailing_number(part)
                    if num and part[:-len(num)]:
                        out.append(part[:-len(num)][0])
                        out.append(num)
                    elif num:
                        out.append(num)
                    else:
                        out.append(part[0])
            return ''.join(out)

        # --- Azure-style concatenated names: westeurope, northeurope, eastus, westus2, uksouth ---
        # Leading compass + rest (westeurope, eastus, westus2)
        for name in compass:
            if region.startswith(name) and len(region) > len(name):
                rest = region[len(name):]
                ca = compass_abbrev(name)
                # rest may be geography (+ optional number), e.g. europe, us, us2
                num = trailing_number(rest)
                geo = rest[:-len(num)] if num else rest
                if geo:
                    return ca + geo_token(geo) + num
                return ca + num

        # Trailing compass (uksouth, australiaeast)
        for name in compass:
            if region.endswith(name) and len(region) > len(name):
                geo = region[:-len(name)]
                ca = compass_abbrev(name)
                return geo_token(geo) + ca

        # --- Logical / non-cloud labels (libvirt/esxifree lab names): keep alnum only ---
        cleaned = re.sub(r'[^a-z0-9]', '', region)
        return cleaned
