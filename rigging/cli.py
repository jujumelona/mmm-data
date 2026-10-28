"""Headless CLI surface sharing the same safe authoring core as MCP."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
from native.inp08 import parse, inspect
from .contracts import validate_manifest, make_anchor, FORMAT
from .deform import propose_keyform
from .handoff import manual_handoff, binding_vertex_slice
from .transactions import execute_transaction
from .quality import inspect_geometry


def main(argv=None):
    p=argparse.ArgumentParser(description='Independent 0.8 Inochi AI rigging helper')
    sub=p.add_subparsers(dest='command',required=True)
    inspectp=sub.add_parser('inspect'); inspectp.add_argument('model')
    validatep=sub.add_parser('validate-anchors'); validatep.add_argument('model'); validatep.add_argument('manifest')
    proposal=sub.add_parser('propose'); proposal.add_argument('model'); proposal.add_argument('manifest');proposal.add_argument('config');proposal.add_argument('--out',required=True)
    handoff=sub.add_parser('manual-handoff')
    handoff.add_argument('model');handoff.add_argument('node_guid')
    handoff.add_argument('--anchors',default='')
    sl=sub.add_parser('binding-slice')
    sl.add_argument('model');sl.add_argument('node_guid');sl.add_argument('parameter_guid')
    sl.add_argument('binding_index',type=int);sl.add_argument('x',type=int);sl.add_argument('y',type=int)
    sl.add_argument('--start',type=int,default=0);sl.add_argument('--limit',type=int,default=256)
    audit=sub.add_parser('geometry-audit')
    audit.add_argument('model')
    audit.add_argument('--no-pairs',action='store_true')
    tx=sub.add_parser('transaction')
    tx.add_argument('model')
    tx.add_argument('batch')
    tx.add_argument('--out',default=None)
    tx.add_argument('--commit',action='store_true')
    tx.add_argument('--strict-pairs',action='store_true')
    a=p.parse_args(argv)
    src=Path(a.model).read_bytes();doc,_,tail=parse(src)
    if a.command=='geometry-audit':data=inspect_geometry(doc,include_pairs=not a.no_pairs)
    elif a.command=='transaction':
        batch=json.loads(Path(a.batch).read_text(encoding='utf8'))
        data=execute_transaction(a.model,batch,destination=a.out,commit=a.commit,strict_pairs=a.strict_pairs)
    elif a.command=='inspect':data={'source_sha256':hashlib.sha256(src).hexdigest(),**inspect(doc)}
    elif a.command=='validate-anchors':data=validate_manifest(doc,src,json.loads(Path(a.manifest).read_text(encoding='utf8')))
    elif a.command=='manual-handoff':
        anchors=json.loads(Path(a.anchors).read_text(encoding='utf8')) if a.anchors else None
        data=manual_handoff(doc,src,a.node_guid,anchors=anchors)
    elif a.command=='binding-slice':
        data=binding_vertex_slice(doc,src,a.node_guid,a.parameter_guid,a.binding_index,[a.x,a.y],a.start,a.limit)
    elif a.command=='propose':
        data=propose_keyform(doc,src,json.loads(Path(a.manifest).read_text(encoding='utf8')),
                             json.loads(Path(a.config).read_text(encoding='utf8')))
        out=Path(a.out)
        if out.exists():p.error('refusing to overwrite output')
        out.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf8')
        data={'saved_plan':str(out),'candidate_count':len(data['patches']),'model_unchanged':True}
    print(json.dumps(data,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
