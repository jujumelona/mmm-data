"""Safe geometry guards independent of external rendering library."""
from math import isfinite

def area(a,b,c):
    return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])

def geometry_errors(verts,offsets,triangles, min_ratio=.05,max_ratio=5.):
    bad=0
    for tri in triangles:
        if len(tri)!=3 or any(type(i)!=int or i<0 or i>=len(verts) for i in tri) or len(set(tri))<3:
            return len(triangles)+1
        n=area(*(verts[j] for j in tri))
        posed=[[verts[j][k]+offsets[j][k] for k in (0,1)] for j in tri]
        p=area(*posed)
        if not isfinite(n) or not isfinite(p) or abs(n)<=1e-9 or p*n<=0 or abs(p/n)<min_ratio or abs(p/n)>max_ratio:
            bad+=1
    return bad
