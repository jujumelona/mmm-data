"""Headless CLI surface sharing the same safe authoring core as MCP."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from native.inp08 import parse, inspect
from .contracts import validate_manifest, make_anchor, FORMAT
from .deform import propose_keyform


def main(argv=None):
    p=argparse.ArgumentParser(description='Independent 0.8 Inochi AI rigging helper')
    sub=p.add_subparsers(dest='command',required=True)
    inspectp=sub.add_parser('inspect'); inspectp.add_argument('model')
    validatep=sub.add_parser('validate-anchors'); validatep.add_argument('model'); validatep.add_argument('manifest')
    proposal=sub.add_parser('propose'); proposal.add_argument('model'); proposal.add_argument('manifest');proposal.add_argument('config');proposal.add_argument('--out',required=True)
    a=p.parse_args(argv)
    src=Path(a.model).read_bytes();doc,_,tail=parse(src)
    if a.command=='inspect':data={'source_sha256':hashlib.sha256(src).hexdigest(),**inspect(doc)}
    elif a.command=='validate-anchors':data=validate_manifest(doc,src,json.loads(Path(a.manifest).read_text(encoding='utf8')))
    elif a.command=='propose':
        data=propose_keyform(doc,src,json.loads(Path(a.manifest).read_text(encoding='utf8')),
                             json.loads(Path(a.config).read_text(encoding='utf8')))
        out=Path(a.out)
        if out.exists():p.error('refusing to overwrite output')
        out.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')
        data={'saved_plan':str(out),'candidate_count':len(data['patches']),'model_unchanged':True}
    print(json.dumps(data,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
