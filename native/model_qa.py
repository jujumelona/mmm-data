"""Real INP1 deformation snapshot structural preflight.
Does not attempt to render hierarchy/physics or assert aesthetic quality.
"""
import argparse
import json
import math
from pathlib import Path
import sys
from inp08 import read_model, extract_samples, inspect, FormatError, atomic_write
from local_geometry import geometry_errors


def run(document):
    stats=inspect(document)
    samples=extract_samples(document)
    results=[]
    for s in samples['samples']:
        offsets=[[p[0]-n[0],p[1]-n[1]] for p,n in zip(s['posed'],s['neutral'])]
        failures=geometry_errors(s['neutral'],offsets,s['triangles'])
        results.append({'part':s['part'],'pose':s['pose'],'triangleFailures':failures,'triangles':len(s['triangles'])})
    critical=sum(r['triangleFailures'] for r in results)
    issues=samples['warnings']
    return {'format':'inochi-authoring.native-qa.v1','model':stats['model_name'],
       'meshNodeCount':len(stats['mesh_nodes']),'parameterCount':len(stats['parameters']),
       'samplesChecked':len(results),'failedTriangles':critical,'bindingsUninspectable':issues,
       'geometryPass':critical==0 and not issues,'results':results,
       'scope':'Individual mesh deformation keyforms only; hierarchy, masking, textures, runtime visual appearance and physics not simulated.'}


def main():
    p=argparse.ArgumentParser()
    p.add_argument('model',type=Path)
    p.add_argument('--output',type=Path)
    args=p.parse_args()
    try:
        doc,_,_=read_model(args.model)
        report=run(doc)
        output=json.dumps(report,ensure_ascii=False,indent=2)
        if args.output:
            if args.output.exists():raise FormatError('refusing overwrite')
            atomic_write(args.output,output.encode('utf8'))
        else:print(output)
        if not report['geometryPass']:sys.exit(1)
    except (OSError,ValueError,TypeError) as e:
        print(f'ERROR: {e}',file=sys.stderr)
        sys.exit(2)

if __name__=='__main__':main()
