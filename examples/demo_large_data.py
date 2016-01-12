#%%
try:
    %load_ext autoreload
    %autoreload 2
    print 1
except:
    print 'NOT IPYTHON'
import sys
import numpy as np
import scipy.io as sio

sys.path.append('../SPGL1_python_port')
import ca_source_extraction as cse
#%
from matplotlib import pyplot as plt
from time import time
import pylab as pl
from scipy.sparse import coo_matrix
import scipy
from sklearn.decomposition import NMF
import tempfile
import os
import tifffile
import subprocess
import time as tm
from time import time
#import pandas as pd
import calblitz as cb
#% for caching
caching=1

if caching:
    import tempfile
    import shutil
    import os

#% TYPE DECONVOLUTION
#deconv_type='debug'
deconv_type='spgl1'
large_data=False
remove_baseline=False
window_baseline=700
quantile_baseline=.1
    

#%%
if 0:
    m=cb.load('k26_v1_176um_target_pursuit_001_005.hdf5')
    m=m-np.percentile(m,8)
    m,shifts,xcorr,template=m.motion_correct()
    m.save('k26_v1_176um_target_pursuit_001_005_mc.hdf5')

#%%
reload=1
if not reload:
#    t = tifffile.TiffFile(filename) 
#    Y = t.asarray().astype(dtype=np.float32)
#    t.close()
    Y=cb.load('k26_v1_176um_target_pursuit_001_005_mc.hdf5')   
    Y=Y-np.percentile(Y,8)
    #Y=np.asarray(Y[:1500,-200:,-200:])
    Y=np.asarray(Y[:1500])
    Y = np.transpose(Y,(1,2,0))
    d1,d2,T=Y.shape
    Yr=np.reshape(Y,(d1*d2,T),order='F')
    if remove_baseline:        
        Yr_begin=Yr[:,:99].copy()
        Yr=Yr-pd.rolling_quantile(Yr.T,window_baseline,quantile_baseline,min_periods=100,center=True).T
        Yr[:,:99]=Yr_begin-np.percentile(Yr_begin,quantile_baseline*100,axis=1)[:,None]    
        Y=np.reshape(Yr,(d1,d2,T),order='F')
    np.save('Y',Y)
    np.save('Yr',Yr)
#%    
if caching:
    Y=np.load('Y.npy',mmap_mode='r')
    Yr=np.load('Yr.npy',mmap_mode='r')        
else:
    Y=np.load('Y.npy')
    Yr=np.load('Yr.npy') 
    
d1,d2,T=Y.shape

#%%
if not large_data:
    Cn = cse.local_correlations(Y)
else:
    Cn=np.mean(Y,axis=2) 
    
#%%
n_processes=6
n_pixels_per_process=d1*d2/n_processes/2
p=2;

preprocess_params={ 'sn':None, 'g': None, 'noise_range' : [0.25,0.5], 'noise_method':'logmexp',
                    'n_processes':n_processes, 'n_pixels_per_process':n_pixels_per_process,   
                    'compute_g':False, 'p':p,   
                    'lags':5, 'include_noise':False, 'pixels':None}
init_params = { 
                    'K':30,'gSig':[7,7],'gSiz':[15,15], 
                    'ssub':2,'tsub':3,
                    'nIter':5, 'use_median':False, 'kernel':None,
                    'maxIter':5
                    }
#%% start cluster for efficient computation
print "Starting Cluster...."
sys.stdout.flush()    
pq=subprocess.Popen(["ipcluster start -n " + str(n_processes)],shell=True) 
tm.sleep(6)   
#%% PREPROCESS DATA
t1 = time()
Yr,sn,g=cse.preprocess_data(Yr,**preprocess_params)
print time() - t1 # 
#%%
#'sn' : sn,
spatial_params = {               
                'd1':d1,  'd2':d2, 'dist':3,  'min_size':3, 'max_size':8, 'method' : 'ellipse',               
                'n_processes':n_processes,'n_pixels_per_process':n_pixels_per_process,'backend':'ipyparallel',
                'memory_efficient':False
                }
temporal_params = {
#                'bl':None,  'c1':None, 'g':None, 'sn' : None,
                'ITER':2, 'method':deconv_type, 'p':p,
                'n_processes':n_processes,'backend':'ipyparallel',
                'memory_efficient':False,                                
                'bas_nonneg':True,  
                'noise_range':[.25,.5], 'noise_method':'logmexp', 
                'lags':5, 'fudge_factor':1., 
                'verbosity':False
                }
#%%
filename='./temp_pre_initialize'
myvars=[[key,locals()[key]]  for key in locals().keys() if (type(locals()[key]) in [np.ndarray,dict,np.matrixlib.defmatrix.matrix]
                                                                or np.isscalar(locals()[key])) 
                                                                and key[0] != '_' and key not in  ['Out','In']]
mydict={key:val for key,val in myvars}
np.savez(filename,**mydict)
del myvars,mydict

#%%
t1 = time()
Ain, Cin, b_in, f_in, center=cse.initialize_components(Y, **init_params)                                                    
print time() - t1 # 
#%%
plt2 = plt.imshow(Cn,interpolation='None')
plt.colorbar()
plt.scatter(x=center[:,1], y=center[:,0], c='m', s=40)
crd = cse.plot_contours(coo_matrix(Ain[:,::-1]),Cn,thr=0.9)
plt.axis((-0.5,d2-0.5,-0.5,d1-0.5))
plt.gca().invert_yaxis()
pl.show()
#%% PROBLEM LOT OF TIME SPENT ON MATRIX MULTIPLICATION
t1 = time()
A,b,Cin = cse.update_spatial_components_parallel(Yr, Cin, f_in, Ain, sn=sn, **spatial_params)
t_elSPATIAL = time() - t1
print t_elSPATIAL 
    
#%%
crd = cse.plot_contours(A,Cn,thr=0.9)
#%%
filename='./temp_pre_temporal'
myvars=[[key,locals()[key]]  for key in locals().keys() if (type(locals()[key]) in [np.ndarray,dict,type(A),np.matrixlib.defmatrix.matrix]
                                                                or np.isscalar(locals()[key])) 
                                                                and key[0] != '_' and key not in  ['Out','In']]
mydict={key:val for key,val in myvars}
np.savez(filename,**mydict)
del myvars,mydict
#%% restart cluster
if caching:
    print "Stopping  and restarting cluster to avoid unnencessary use of memory...."
    sys.stdout.flush()  
    qp=subprocess.Popen(["ipcluster stop"],shell=True)
    tm.sleep(5)
    print "restarting cluster..."
    sys.stdout.flush() 
    qp=subprocess.Popen(["ipcluster start -n " + str(n_processes)],shell=True) 
    tm.sleep(10)
#%% update_temporal_components
t1 = time()
C,f,Y_res,S,bl,c1,neurons_sn,g = cse.update_temporal_components_parallel(Yr,A,b,Cin,f_in,bl=None,c1=None,sn=None,g=None,**temporal_params)
t_elTEMPORAL2 = time() - t1
print t_elTEMPORAL2 # took 98 sec   
#%%
if 0: 
    A_or, C_or, srt = cse.order_components(A,C)
    cse.view_patches(Yr,coo_matrix(A_or),C_or,b,f,d1,d2,secs=1)
elif 0:
    cse.view_patches(Yr,A,C,b,f,d1,d2,secs=0)
#    C_or=C
#    A_or=A.todense()
#    srt=range(30)
#%%
filename='./pre_merge'
myvars=[[key,locals()[key]]  for key in locals().keys() if (type(locals()[key]) in [np.ndarray,dict,type(A),np.matrixlib.defmatrix.matrix]
                                                                or np.isscalar(locals()[key])) 
                                                                and key[0] != '_' and key not in  ['Out','In']]
mydict={key:val for key,val in myvars}
np.savez(filename,**mydict)
del myvars,mydict

#%%
t1 = time()
A_m,C_m,nr_m,merged_ROIs,S_m,bl_m,c1_m,sn_m,g_m=cse.mergeROIS_parallel(Y_res,A,b,C,f,S,sn,temporal_params, spatial_params, bl=bl, c1=c1, sn=neurons_sn, g=g, thr=0.8, mx=50)
t_elMERGE = time() - t1
print t_elMERGE  
#%%
if 0:
    A_or, C_or, srt = cse.order_components(A_m,C_m)
    cse.view_patches(Yr,coo_matrix(A_or),C_or,b,f, d1,d2,secs=1)
#%%

#%%
#from scipy.io import loadmat
#ld = loadmat('./after_merge.mat') 
#Ain_mat=ld['Ain']
#Cin_mat=ld['Cin']
#Yr_mat=ld['Yr']
#Y_mat=ld['Y']
#f_in_mat=ld['fin']
#sn_mat=ld['sn']
#A_mat=ld['A']
#b_mat=ld['b']
#C_mat=ld['C']
#f_mat=ld['f']
#Y_res_mat=ld['Y_res']
#P_mat=ld['P']
#S_mat=ld['S']
#
#neurons_sn_mat=ld['neurons_sn'].flatten()
#bl_mat=ld['bl'].flatten()
#c1_mat=ld['c1'].flatten()
#g_mat=ld['g']
#g_mat=[[p1,p2] for p1,p2 in zip(g_mat[0],g_mat[1])]
#
#A_m_mat=ld['Am']
#K_m_mat=ld['K_m']
#C_m_mat=ld['Cm']
#merged_ROIs_mat=ld['merged_ROIs']
#P_m_mat=ld['P']
#S_m_mat=ld['Sm']
#%%
crd = cse.plot_contours(A_m,Cn,thr=0.9)
#%%
t1 = time()
A2,b2,C2 = cse.update_spatial_components_parallel(Yr, C_m, f, A_m, sn=sn, **spatial_params)
#C2,f2,Y_res2,S2,bl2,c12,neurons_sn2,g21 = cse.update_temporal_components_parallel(Yr,A2,b2,C2,f,bl=bl_m,c1=c1_m,sn=sn_m,g=g_m,**temporal_params)
C2,f2,Y_res2,S2,bl2,c12,neurons_sn2,g21 = cse.update_temporal_components_parallel(Yr,A2,b2,C2,f,bl=None,c1=None,sn=None,g=None,**temporal_params)
print time() - t1 # 100 seconds
#%%
if 0:
    A_or, C_or, srt = cse.order_components(A2,C2)
    cse.view_patches(Yr,coo_matrix(A_or),C_or,b2,f2, d1,d2,secs=1)
    
#%% STOP CLUSTER
print "Stopping Cluster...."
sys.stdout.flush()  
q=subprocess.Popen(["ipcluster stop"],shell=True)
#%%
filename='./final'
myvars=[[key,locals()[key]]  for key in locals().keys() if (type(locals()[key]) in [np.ndarray,dict,type(A)] or np.isscalar(locals()[key])) and key[0] != '_' and key not in  ['Out','In']]
mydict={key:val for key,val in myvars}
np.savez(filename,**mydict)
del myvars,mydict
