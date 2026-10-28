"""Fail-closed, no-overwrite and auditable INP 0.8 batch editor.

All operations apply to a private cloned puppet; after full structural validation
and readback, one new destination is published atomically. A failure leaves no
partial puppet and never modifies the source. Revisions are source SHA guarded.
"""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
from native.inp08 import parse,encode,atomic_write,apply_keyform
from .topology import subdivide_once
from .quality import inspect_geometry
from .agent_editor import apply_agent_edit

FORMAT='inochi-ai-rigging.transaction.v1'

class TransactionError(ValueError):pass


def execute_transaction(model_path:str|Path, batch:dict, *, destination:str|Path|None=None,
                        commit:bool=False, strict_pairs:bool=False)->dict:
    src=Path(model_path).resolve()
    original=src.read_bytes()
    sha=hashlib.sha256(original).hexdigest()
    if not isinstance(batch,dict) or set(batch)-{'format','source_sha256','edits','request_id'}:
        raise TransactionError('invalid or privileged batch fields')
    if batch.get('format')!=FORMAT or batch.get('source_sha256')!=sha:
        raise TransactionError('stale or unsupported source revision')
    request_id=batch.get('request_id')
    if not isinstance(request_id,str) or not request_id.strip() or len(request_id)>128:
        raise TransactionError('nonempty request_id of max 128 characters required')
    operations=batch.get('edits')
    if not isinstance(operations,list) or not operations:
        raise TransactionError('batch requires nonempty edits')
    if commit:
        # Commit is never allowed to disable the conservative composite-pose gate.
        strict_pairs=True
    if commit and destination is None:
        raise TransactionError('commit requires separate destination')
    if destination is not None:
        out=Path(destination).resolve()
        if out==src or out.exists():raise TransactionError('source overwrite or existing output refused')
        if out.suffix.lower() not in ('.inp','.inx'):
            raise TransactionError('output must have .inp or .inx extension')
    doc,_,tail=parse(original)
    clone=copy.deepcopy(doc)
    report=[]
    targets=set()
    for i,op in enumerate(operations):
        if not isinstance(op,dict) or 'op' not in op:
            raise TransactionError(f'edit[{i}]: missing op')
        kind=op['op']
        if kind=='set_new_keyform':
            if set(op)-{'op','parameter','parameter_guid','node_guid','key_index','vertex_offsets'}:
                raise TransactionError(f'edit[{i}]: forbidden keyform field')
            key=(kind,op.get('parameter_guid') or op.get('parameter'),op.get('node_guid'),tuple(op.get('key_index',[])))
            # Structural target collision with other mutations refuses ambiguous plans.
            if key in targets:raise TransactionError('duplicate keyform edit target')
            targets.add(key)
            # No 'allow_replace' or 'allow_unsafe' fields can be supplied.
            result=apply_keyform(clone,{k:v for k,v in op.items() if k!='op'})
        elif kind=='subdivide_mesh':
            if set(op)-{'op','node_guid','expected_mesh_sha256'}:
                raise TransactionError(f'edit[{i}]: forbidden mesh field')
            key=(kind,op.get('node_guid'))
            if key in targets:raise TransactionError('duplicate subdivision target')
            targets.add(key)
            result=subdivide_once(clone,op['node_guid'],expected_mesh_sha256=op['expected_mesh_sha256'])
        elif kind in ('set_node_property','set_parameter_property','edit_mesh_vertices',
                      'edit_mesh_uvs','replace_deform_keyform','replace_binding_value_keyform'):
            result=apply_agent_edit(clone,op)
        else:
            raise TransactionError(f'edit[{i}]: unknown operation {kind!r}')
        report.append({'index':i,'operation':kind,'result':result})
    quality=inspect_geometry(clone,include_pairs=True)
    if not quality['individual_geometry_pass']:
        raise TransactionError(f"edited puppet has {len(quality['individual_failures'])} invalid authored keyforms")
    if strict_pairs and not quality['additive_proxy_pair_pass']:
        raise TransactionError(f"edited puppet has {len(quality['additive_proxy_pair_failures'])} unsafe additive-proxy pairs")
    updated=encode(clone,tail)
    parsed,_,newtail=parse(updated)
    if parsed!=clone or newtail!=tail:
        raise TransactionError('binary roundtrip or texture/extension integrity failure')
    receipt={
        'format':'inochi-ai-rigging.transaction-receipt.v1',
        'request_id':request_id,'original_sha256':sha,
        'candidate_sha256':hashlib.sha256(updated).hexdigest(),
        'source_preserved':True,'texture_and_extensions_byte_identical':True,
        'actions':report,'quality':quality,
        'committed':False,'creator_render_tested':False,
    }
    if commit:
        atomic_write(out,updated)
        # Verify committed bytes rather than merely write status.
        if hashlib.sha256(out.read_bytes()).hexdigest()!=receipt['candidate_sha256']:
            raise TransactionError('published output failed checksum verification')
        receipt['committed']=True
        receipt['destination']=str(out)
    return receipt
