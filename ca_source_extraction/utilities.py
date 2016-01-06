# -*- coding: utf-8 -*-
"""A set of utilities, mostly for post-processing and visualization
Created on Sat Sep 12 15:52:53 2015

@author epnev
"""

import numpy as np
from scipy.sparse import spdiags, diags
from matplotlib import pyplot as plt
from pylab import pause
import sys


def local_correlations(Y,eight_neighbours=False, swap_dim = True):
     """Computes the correlation image for the input dataset Y
     Inputs:
     Y:   np.ndarray (3D)
          Input movie data in 3D format
     eight_neibhbours: Boolean
          Use 8 neighbors if true, and 4 if false (default = False)
     swap_dim: Boolean
          True indicates that time is listed in the last axis of Y (matlab format)
      and moves it in the front
     
      Output:
        rho d1 x d2 matrix, cross-correlation with adjacent pixels
     """
     
     if swap_dim:
         Y = np.transpose(Y,tuple(np.hstack((Y.ndim-1,range(Y.ndim)[:-1]))))
    
     rho = np.zeros(np.shape(Y)[1:3])
     w_mov = (Y - np.mean(Y, axis = 0))/np.std(Y, axis = 0)
 
     rho_h = np.mean(np.multiply(w_mov[:,:-1,:], w_mov[:,1:,:]), axis = 0)
     rho_w = np.mean(np.multiply(w_mov[:,:,:-1], w_mov[:,:,1:,]), axis = 0)
     
     if True:
         rho_d1 = np.mean(np.multiply(w_mov[:,1:,:-1], w_mov[:,:-1,1:,]), axis = 0)
         rho_d2 = np.mean(np.multiply(w_mov[:,:-1,:-1], w_mov[:,1:,1:,]), axis = 0)


     rho[:-1,:] = rho[:-1,:] + rho_h
     rho[1:,:] = rho[1:,:] + rho_h
     rho[:,:-1] = rho[:,:-1] + rho_w
     rho[:,1:] = rho[:,1:] + rho_w
     
     if eight_neighbours:
         rho[:-1,:-1] = rho[:-1,:-1] + rho_d2
         rho[1:,1:] = rho[1:,1:] + rho_d1
         rho[1:,:-1] = rho[1:,:-1] + rho_d1
         rho[:-1,1:] = rho[:-1,1:] + rho_d2
          
     if eight_neighbours:
         neighbors = 8 * np.ones(np.shape(Y)[1:3])  
         neighbors[0,:] = neighbors[0,:] - 3;
         neighbors[-1,:] = neighbors[-1,:] - 3;
         neighbors[:,0] = neighbors[:,0] - 3;
         neighbors[:,-1] = neighbors[:,-1] - 3;
         neighbors[0,0] = neighbors[0,0] + 1;
         neighbors[-1,-1] = neighbors[-1,-1] + 1;
         neighbors[-1,0] = neighbors[-1,0] + 1;
         neighbors[0,-1] = neighbors[0,-1] + 1;
     else:
         neighbors = 4 * np.ones(np.shape(Y)[1:3]) 
         neighbors[0,:] = neighbors[0,:] - 1;
         neighbors[-1,:] = neighbors[-1,:] - 1;
         neighbors[:,0] = neighbors[:,0] - 1;
         neighbors[:,-1] = neighbors[:,-1] - 1;   

     rho = np.divide(rho, neighbors)

     return rho
     
def order_components(A,C):
     """Order components based on their maximum temporal value and size
     Inputs:
     A:   sparse matrix (d x K)
          spatial components
     C:   matrix or np.ndarray (K x T)
          temporal components
          
     A_or:     ordered spatial components
     C_or:     ordered temporal components
     srt:      sorting mapping
     """
     A = np.array(A.todense())
     nA2 = np.sqrt(np.sum(A**2,axis=0))
     A = np.array(np.matrix(A)*diags(1/nA2,0))
     nA4 = np.sum(A**4,axis=0)**0.25
     C = np.array(diags(nA2,0)*np.matrix(C))
     mC = np.ndarray.max(np.array(C),axis=1)
     srt = np.argsort(nA4**mC)[::-1]
     A_or = A[:,srt]
     C_or = C[srt,:]
          
     return A_or, C_or, srt
     

def extract_DF_F(Y,A,C,i=None):
    """Extract DF/F values from spatial/temporal components and background
     Inputs:
     Y: np.ndarray
           input data (d x T)
     A: sparse matrix of np.ndarray 
           Set of spatial including spatial background (d x K)
     C: matrix
           Set of temporal components including background (K x T)
           
     Output:
     C_df: matrix 
          temporal components in the DF/F domain
     Df:  np.ndarray
          vector with baseline values for each trace
    """
    A2 = A.copy()
    A2.data **= 2
    nA2 = np.squeeze(np.array(A2.sum(axis=0)))
    A = A*diags(1/nA2,0)
    C = diags(nA2,0)*C         
     
    #if i is None:
    #    i = np.argmin(np.max(A,axis=0))

    Y = np.matrix(Y)         
    Yf =  A.transpose()*(Y - A*C) #+ A[:,i]*C[i,:])
    Df = np.median(np.array(Yf),axis=1)
    C_df = diags(1/Df,0)*C
             
    return C_df, Df


     
def com(A,d1,d2):
    """Calculation of the center of mass for spatial components
     Inputs:
     A:   np.ndarray 
          matrix of spatial components (d x K)
     d1:  int
          number of pixels in x-direction
     d2:  int
          number of pixels in y-direction
    
     Output:
     cm:  np.ndarray
          center of mass for spatial components (K x 2)
    """
    nr = np.shape(A)[-1]
    Coor=dict();
    Coor['x'] = np.kron(np.ones((d2,1)),np.expand_dims(range(d1),axis=1)); 
    Coor['y'] = np.kron(np.expand_dims(range(d2),axis=1),np.ones((d1,1)));
    cm = np.zeros((nr,2));        # vector for center of mass							   
    cm[:,0]=np.dot(Coor['x'].T,A)/A.sum(axis=0)
    cm[:,1]=np.dot(Coor['y'].T,A)/A.sum(axis=0)       
    
    return cm
     
     
def view_patches(Yr,A,C,b,f,d1,d2,secs=1):
    """view spatial and temporal components (secs=0 interactive)
     Yr:        np.ndarray 
            movie in format pixels (d) x frames (T)
     A:     sparse matrix
                matrix of spatial components (d x K)
     C:     np.ndarray
                matrix of temporal components (K x T)
     b:     np.ndarray
                spatial background (vector of length d)

     f:     np.ndarray
                temporal background (vector of length T)
     d1,d2: np/ndarray
                frame dimensions
     secs: float
                number of seconds in between component scrolling. secs=0 means interactive (click to scroll)
             
    """    
    plt.ion()
    nr,T = C.shape    
    nA2 = np.sum(np.array(A.todense())**2,axis=0)
    Y_r = np.array(spdiags(1/nA2,0,nr,nr)*(A.T*np.matrix(Yr-b[:,np.newaxis]*f[np.newaxis] - A.dot(C))) + C)    
    A=A.todense()
#    Y_r = (Yr-b.dot(f)).T.dot(A.todense()).T/nA2[:,None]#-bl[:,None]
#    Y_r=[];
#    
#    Atmp=A.copy()
#    Ctmp=C.copy()
#    for ii in range(C.shape[0]):
#        print ii
#        old_c=Ctmp[ii,:]
#        old_a=Atmp[:,ii]        
#        Atmp[:,ii]=0  
#        Ctmp[ii,:]=0
#        Y_r.append((Yr-b.dot(f)- Atmp.dot(Ctmp)).T.dot(A[:,ii]).T/nA2[ii])
#        Atmp[:,ii]=old_a  
#        Ctmp[ii,:]=old_c                
#    Y_r=np.asarray(Y_r)
    
    fig = plt.figure()
    thismanager = plt.get_current_fig_manager()
    thismanager.toolbar.pan()
    print('In order to scroll components you need to click on the plot')
    sys.stdout.flush()  
    for i in range(nr+1):
        if i < nr:
            ax1 = fig.add_subplot(2,1,1)
            plt.imshow(np.reshape(np.array(A[:,i]),(d1,d2),order='F'),interpolation='None')
            ax1.set_title('Spatial component ' + str(i+1))    
            ax2 = fig.add_subplot(2,1,2)
            plt.plot(np.arange(T),np.squeeze(np.array(Y_r[i,:])),'c',linewidth=3) 
            plt.plot(np.arange(T),np.squeeze(np.array(C[i,:])),'r',linewidth=2) 
            ax2.set_title('Temporal component ' + str(i+1)) 
            ax2.legend(labels = ['Filtered raw data','Inferred trace'])
            
            if secs>0:               
                plt.pause(secs) 
            else:
                plt.waitforbuttonpress()   
                
            fig.delaxes(ax2)
        else:
            ax1 = fig.add_subplot(2,1,1)
            plt.imshow(np.reshape(b,(d1,d2),order='F'),interpolation='None')
            ax1.set_title('Spatial background background')    
            ax2 = fig.add_subplot(2,1,2)
            plt.plot(np.arange(T),np.squeeze(np.array(f))) 
            ax2.set_title('Temporal background')      
            
def plot_contours(A,Cn,thr = 0.995, display_numbers = True, max_number = None,cmap=None, **kwargs):
    """Plots contour of spatial components against a background image and returns their coordinates
    Inputs:
     A:   np.ndarray or sparse matrix
               Matrix of Spatial components (d x K)
     Cn:  np.ndarray (2D)
               Background image (e.g. mean, correlation)
     thr: scalar between 0 and 1
               Energy threshold for computing contours (default 0.995)
     display_number:     Boolean
               Display number of ROIs if checked (default True)
     max_number:    int
               Display the number for only the first max_number components (default None, display all numbers)
     cmap:     string
               User specifies the colormap (default None, default colormap)
               
     Output:
     Coor: list of coordinates with center of mass, contour plot coordinates and bounding box for each component
    """
    from  scipy.sparse import issparse
    if issparse(A):
        A = np.array(A.todense())
    else:
         A = np.array(A)
         
    d1,d2 = np.shape(Cn)
    d,nr = np.shape(A)       
    if max_number is None:
        max_number = nr
        
    x,y = np.mgrid[0:d1:1,0:d2:1]    
    
#    fig = plt.figure()
#    ax = fig.add_subplot(111)
    ax = plt.gca()
    plt.imshow(Cn,interpolation=None,cmap=cmap)
    coordinates = []
    cm = com(A,d1,d2)
    for i in range(np.minimum(nr,max_number)):
        pars=dict(kwargs)
        indx = np.argsort(A[:,i],axis=None)[::-1]
        cumEn = np.cumsum(A[:,i].flatten()[indx]**2)
        cumEn /= cumEn[-1]
        Bvec = np.zeros(d)
        Bvec[indx] = cumEn
        Bmat = np.reshape(Bvec,np.shape(Cn),order='F')
        cs = plt.contour(y,x,Bmat,[thr])
        p = cs.collections[0].get_paths()[0]
        v = p.vertices
        pars['CoM'] = np.squeeze(cm[i,:])
        pars['coordinates'] = v           
        pars['bbox'] = [np.floor(np.min(v[:,1])),np.ceil(np.max(v[:,1])),np.floor(np.min(v[:,0])),np.ceil(np.max(v[:,0]))]
        pars['neuron_id'] = i+1
        coordinates.append(pars)        
        
    if display_numbers:
        for i in range(np.minimum(nr,max_number)):
            ax.text(cm[i,1],cm[i,0],str(i+1))
            
    return coordinates
    
def update_order(A):
    '''Determines the update order of the temporal components given the spatial 
    components by creating a nest of random approximate vertex covers
     Input:
     A:    np.ndarray
          matrix of spatial components (d x K)
     
     Outputs:
     O:   list of sets
          list of subsets of components. The components of each subset can be updated in parallel
     lo:  list
          length of each subset
    Written by Eftychios A. Pnevmatikakis, Simons Foundation, 2015
    '''    
    K = np.shape(A)[-1]
    AA = A.T*A
    AA.setdiag(0)
    F = (AA)>0
    F = F.toarray()
    rem_ind = np.arange(K)
    O = []
    lo = []
    while len(rem_ind)>0:
        L = np.sort(app_vertex_cover(F[rem_ind,:][:,rem_ind]))
        if L.size:        
            ord_ind = set(rem_ind) - set(rem_ind[L])
            rem_ind = rem_ind[L]
        else:
            ord_ind = set(rem_ind)
            rem_ind = []
            
        O.append(ord_ind)
        lo.append(len(ord_ind))               
    
    return O[::-1],lo[::-1]
   
def app_vertex_cover(A):
    ''' Finds an approximate vertex cover for a symmetric graph with adjacency 
    matrix A.
     Input:
     A:    boolean 2d array (K x K)
          Adjacency matrix. A is boolean with diagonal set to 0
     
     Output:
     L:   A vertex cover of A
    Written by Eftychios A. Pnevmatikakis, Simons Foundation, 2015
    '''
    
    L = []
    while A.any():
        nz = np.nonzero(A)[0]          # find non-zero edges
        u = nz[np.random.randint(0,len(nz))]
        A[u,:] = False
        A[:,u] = False
        L.append(u)
    
    return np.asarray(L)    
#%%
def save_mat_in_chuncks(Yr,num_chunks,shape,mat_name='mat',axis=0): 
    """ save hdf5 matrix in chunks
    
    Parameters
    ----------
    file_name: str
        file_name of the hdf5 file to be chunked
    shape: tuples
        shape of the original chunked matrix
    idx: list
        indexes to slice matrix along axis
    mat_name: [optional] string
        name prefix for temporary files
    axis: int
        axis along which to slice the matrix   
    
    Returns:
    name of the saved file
            
    """
    
    Yr=np.array_split(Yr,num_chunks,axis=axis)  
    print "splitting array..."
    folder = tempfile.mkdtemp()  
    prev=0
    idxs=[]
    names=[];
    for mm in Yr:
        mm=np.array(mm)
        idxs.append(np.array(range(prev,prev+mm.shape[0])).T)
        new_name = os.path.join(folder, mat_name + '_'+str(prev) +'_'+str(len(idxs[-1])) ) 
        print "Saving " + new_name
        np.save(new_name,mm)
        names.append(new_name)        
        prev=prev+mm.shape[0]    
    
    return {'names':names,'idxs':idxs,'axis':axis,'shape':shape}   

def db_plot(*args,**kwargs):
    plt.plot(*args,**kwargs)
    plt.show()
    pause(1)