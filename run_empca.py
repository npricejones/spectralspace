"""

Usage:
run_empca [-hvgxu] [-m FNAME] [-d DELTR] [-n NVECS]

Options:
    -h, --help
    -v, --verbose
    -g, --generate                  Option to generate everything from scratch.
    -u, --usemad                    Option to use M.A.D. instead of variance.
    -x, --hidefigs                  Option to hide figures.
    -m FNAME, --model FNAME         Provide a pickle file containing a Sample model (see residuals.py)
    -d DELTR, --delt DELTR          Provide an R2 difference at which to cutoff iteration [default: 0]
    -n NVECS, --nvecs NVECS         Specify number of empca vectors [default: 5]

"""

import docopt
import empca
reload(empca)
from empca import empca
import numpy as np
import matplotlib.pyplot as plt
from run_residuals import timeIt,weight_residuals
from residuals import doubleResidualHistPlot
import access_spectrum as acs
import os

elems = ['Al','Ca','C','Fe','K','Mg','Mn','Na','Ni','N','O','Si','S','Ti','V']
#elems = ['C','Fe','K','Mg','Ni','N','O','Si','S']
aspcappix = 7214
default_colors = {0:'b',1:'g',2:'r',3:'c'}
default_markers = {0:'o',1:'s',2:'v',3:'D'}
default_sizes = {0:10,1:8,2:10,3:8}

def pix_empca(model,residual,errs,empcaname,nvecs=5,gen=False,verbose=False,nstars=5,deltR2=0,usemad=True):
    """
    Runs EMPCA on a set of residuals with dimension of aspcappix.
    """
    if os.path.isfile(empcaname) and not gen:
        empcamodel,empcamodel_weight,weights = acs.pklread(empcaname)
    elif not os.path.isfile(empcaname) or gen:
        # Identify pixels at which there are more than nstars stars
        goodpix = ([i for i in range(aspcappix) if np.sum(residual[i].mask) < residual.shape[1]-nstars],)
        print 'badpix, ',[i for i in range(aspcappix) if i not in goodpix[0]]
        # Create new array to feed to EMPCA with only good pixels
        empca_res = residual[goodpix].T
        # Create a set of weights for EMPCA, setting weight to zero if value is masked
        mask = (empca_res.mask==False)
        weights = mask.astype(float)
        empcamodel,runtime1 = timeIt(empca,empca_res.data,weights = weights,nvec=nvecs,deltR2=deltR2,mad=usemad)
        # Change weights to incorporate flux uncertainties
        sigmas = errs.T[goodpix].T
        weights[mask] = 1./sigmas[mask]**2
        empcamodel_weight,runtime2 = timeIt(empca,empca_res.data,weights = weights,nvec=nvecs,deltR2=deltR2,mad=usemad)
        if verbose:
            print 'Pixel runtime (unweighted):\t', runtime1/60.,' min'
            print 'Pixel runtime (weighted):\t', runtime2/60.,' min'
        acs.pklwrite(empcaname,[empcamodel,empcamodel_weight,weights])
    return empcamodel,empcamodel_weight,weights

def resize_pix_eigvecs(residual,empcamodel,nstars=5):
    goodpix = ([i for i in range(aspcappix) if np.sum(residual[i].mask) < residual.shape[1]-nstars],)
    badpix = ([i for i in range(aspcappix) if i not in goodpix],)
    # Resize eigenvectors appropriately and mask missing elements
    empcamodel.eigvec.resize((nvecs,aspcappix))
    for ind in range(len(elems)):
        for vec in range(nvecs):
            newvec = np.ma.masked_array(np.zeros((aspcappix)),mask = np.zeros((aspcappix)))
            newvec[goodpix] = empcamodel.eigvec[vec][:len(goodpix[0])]
            newvec.mask[badpix] = 1
            empcamodel.eigvec[vec] = newvec

def elem_empca(model,residual,errs,empcaname,nvecs=5,gen=False,verbose=False,deltR2=0,usemad=True):
    if nvecs > len(elems):
        nvecs = len(elems) - 1
    if os.path.isfile(empcaname) and not gen:
        empcamodel,empcamodel_weight,weights = acs.pklread(empcaname)
    elif not os.path.isfile(empcaname) or gen:
        mask = (residual.T.mask==False)
        weights = mask.astype(float)
        empcamodel,runtime1 = timeIt(empca,residual.T.data,weights = weights,nvec=nvecs,deltR2=deltR2,mad=usemad)
        weights[mask] = 1./errs.T[mask]
        empcamodel_weight,runtime2 = timeIt(empca,residual.T.data,weights = weights,nvec=nvecs,deltR2=deltR2,mad=usemad)
        if verbose:
            print 'Element runtime (unweighted):\t', runtime1/60.,' min'
            print 'Element runtime (weighted):\t', runtime2/60.,' min'
        acs.pklwrite(empcaname,[empcamodel,empcamodel_weight,weights])
    return empcamodel,empcamodel_weight,weights

def R2noise(weights,empcamodel,usemad=True):
    """
    Calculate the fraction of variance due to noise.
    """
    if usemad:
        var = empcamodel._unmasked_data_mad2*1.4826**2.
    elif not usemad:
        var = empcamodel._unmasked_data_var
    Vnoise = np.mean(1./(weights[weights!=0]))
    print 'var, Vnoise ',var,Vnoise
    return 1-(Vnoise/var)

def R2(empcamodel,usemad=True):
    """
    For a given EMPCA model object, fill an array with R2 values for a set number of eigenvectors
    """
    nvecs = len(empcamodel.eigvec)
    R2_arr = np.zeros(nvecs+1)
    for vec in range(nvecs+1):
        R2_arr[vec] = empcamodel.R2(vec,mad=usemad)
    return R2_arr

def weight_eigvec(model,nvecs,empcamodel):
    """
    Construct new eigenvectors weighted by element windows.
    """
    neweigvecs = np.zeros((nvecs,len(elems)))
    for ind in range(len(elems)):
        for vec in range(nvecs):
            neweigvecs[vec][ind] = model.weighting(empcamodel.eigvec[vec],elems[ind])
    return neweigvecs

def weight_residual(model,numstars,plot=True,subgroup=False):
    # Create output arrays
    weighted = np.ma.masked_array(np.zeros((len(elems),numstars)))
    weightedsigs = np.ma.masked_array(np.zeros((len(elems),numstars)))
    i=0
    # Cycle through elements
    for elem in elems:
        if subgroup != False:
            match = np.where(model.data[model.subgroup]==subgroup)
            residual = model.residual[subgroup]
            sigma = model.errs[match].T
        elif not subgroup:
            residual = model.residual
            sigma = model.errs.T
        # Weight residuals and sigma values
        weightedr = model.weighting_stars(residual,elem,
                                          model.outName('pkl','resids',elem=elem,
                                                        order = model.order,
                                                        subgroup=subgroup,
                                                        cross=model.cross))
        weighteds = model.weighting_stars(sigma,elem,
                                          model.outName('pkl','sigma',elem=elem,
                                                        order = model.order,
                                                        subgroup=subgroup,
                                                        seed = model.seed))
        print 'weighteds is zero for elem ',elem,' at ',np.where(weighteds==0)

        if plot:
            doubleResidualHistPlot(elem,weightedr[weightedr.mask==False],weighteds[weighteds.mask==False],
                                   model.outName('res','residhist',elem = elem,
                                                 order = model.order,
                                                 cross=model.cross,seed = model.seed,
                                                 subgroup = subgroup),
                                   bins = 50)
        weighted[i] = weightedr
        weightedsigs[i] = weighteds
        i+=1
    return weighted,weightedsigs

def plot_R2(empcamodels,weights,ptitle,savename,labels=None,nvecs=5,usemad=True,hide=True):
    R2noiseval = R2noise(weights,empcamodels[0],usemad=usemad)
    vec_vals = range(0,nvecs+1)
    plt.figure(figsize=(12,10))
    plt.xlim(0,nvecs)
    plt.ylim(0,1)
    plt.fill_between(vec_vals,R2noiseval,1,color='r',alpha=0.2)
    if R2noiseval > 0:
        plt.text(nvecs-(nvecs/5.),R2noiseval+0.1,'R2_noise = {0:2f}'.format(R2noiseval))
    elif R2noiseval <= 0:
        plt.text(nvecs-(nvecs/5.),0.1,'R2_noise = {0:2f}'.format(R2noiseval))
    plt.axhline(R2noiseval,linestyle='--',color='k',label='Noise Threshold')
    plt.xlabel('Number of eigenvectors')
    plt.ylabel('Variance explained')
    plt.title(ptitle)
    for e in range(len(empcamodels)):
        R2_vals = R2(empcamodels[e],usemad=usemad)
        if not labels:
            plt.plot(vec_vals,R2_vals,marker='o',linewidth = 3,markersize=8)
        else:
            plt.plot(vec_vals,R2_vals,label=labels[e],marker='o',linewidth = 3,markersize=8)
    if not labels:
        plt.savefig(savename)
    else:
        plt.legend(loc='best')
        plt.savefig(savename)
    if hide:
        plt.close()

def norm_eigvec(eigvec):
    return eigvec/np.sqrt(np.sum(eigvec**2))

def plot_element_eigvec(eigvecs,savenames,mastercolors=default_colors,markers=default_markers,sizes=default_sizes,labels=None,hidefigs=False,nvecs=5):
    
    assert len(eigvecs) <= len(mastercolors)
    assert len(markers) == len(mastercolors)
    assert len(sizes) == len(mastercolors)

    for vec in range(nvecs):
        plt.figure(figsize=(12,10))
        plt.xticks(range(len(elems)),elems)
        plt.axhline(0,color='k')
        plt.xlim(-1,len(elems))
        plt.xlabel('Elements')
        plt.ylabel('Eigenvector')
        plt.title('{0} eigenvector, weighted by element'.format(vec))
        vectors = np.zeros((len(eigvecs),len(elems)))
        e = 0
        for eigvec in eigvecs: 
            vectors[e] = norm_eigvec(eigvec[vec])
            if not labels:
                plt.plot(vectors[e],color=mastercolors[e],marker=markers[e],linestyle='None',markersize=sizes[e])
            else:
                plt.plot(vectors[e],color=mastercolors[e],marker=markers[e],linestyle='None',markersize=sizes[e],label=labels[e])
            e+=1
        for i in range(len(elems)):
            colors = {}
            for v in range(len(vectors)):
                colors[vectors[v][i]] = mastercolors[v]
            order = colors.keys()
            order = sorted(order,key = abs)[::-1]
            for val in order:
                plt.plot([i,i],[0,val],color=colors[val],linewidth=3)
        if not labels:
            plt.savefig(savename)
        else:
            plt.savefig(savenames[vec])
            plt.legend(loc='best')
            plt.close()



if __name__=='__main__':

    # Read in command line arguments
    arguments = docopt.docopt(__doc__)

    verbose = arguments['--verbose']
    gen = arguments['--generate']
    usemad = arguments['--usemad']
    hide = arguments['--hidefigs']
    modelname = arguments['--model']
    deltR2 = float(arguments['--delt'])
    nvecs = int(arguments['--nvecs'])

    model=acs.pklread(modelname)

    nstars = 5

    if model.subgroups[0] != False:
        for subgroup in model.subgroups:
            
            match = np.where(model.data[model.subgroup]==subgroup)
            
            empcaname = model.outName('pkl',content = 'empca',subgroup=subgroup,order = model.order,seed = model.seed,cross=model.cross)
            empcaname = empcaname.split('.pkl')[0]+'_nvec{0}'.format(nvecs)+'.pkl'
            m1,m2,w1 = pix_empca(model,model.residual[subgroup],model.errs[match],empcaname,nvecs=nvecs,gen=gen,verbose=verbose,nstars=nstars,deltR2=deltR2,usemad=usemad)
            
            residual,errs = weight_residual(model,model.numstars[subgroup],plot=True,subgroup=subgroup)
            empcaname = model.outName('pkl',content = 'empca_element',order = model.order,
                                           seed = model.seed,cross=model.cross,subgroup=subgroup)
            empcaname = empcaname.split('.pkl')[0]+'_nvec{0}'.format(nvecs)+'.pkl'
            m3,m4,w2 = elem_empca(model,residual,errs,empcaname,nvecs=nvecs,gen=gen,verbose=verbose,deltR2=deltR2,usemad=usemad)
            
            labels = ['Unweighted EMPCA - raw','Weighted EMPCA - raw']
            savename = './{0}/empca/pix_empcaR2_{1}_order{2}_seed{3}_cross{4}_nvec{5}_MAD{6}.png'.format(model.type,subgroup, model.order,model.seed,model.cross,nvecs,usemad)
            ptitle = 'R2 for {0} from pixel space'.format(subgroup)
            plot_R2([m1,m2],w1,ptitle,savename,labels=None,nvecs=nvecs,usemad=usemad,hide=hide)
            labels = ['Unweighted EMPCA - proc','Weighted EMPCA - proc']
            savename = './{0}/empca/elem_empcaR2_{1}_order{2}_seed{3}_cross{4}_nvec{5}_MAD{6}.png'.format(model.type,subgroup, model.order,model.seed,model.cross,nvecs,usemad)
            ptitle = 'R2 for {0} from element space'.format(subgroup)
            plot_R2([m3,m4],w2,ptitle,savename,labels=None,nvecs=nvecs,usemad=usemad,hide=hide)

            resize_pix_eigvecs(model.residual[subgroup],m1,nstars=nstars)
            resize_pix_eigvecs(model.residual[subgroup],m2,nstars=nstars)

            newm1 = weight_eigvec(model,nvecs,m1)
            newm2 = weight_eigvec(model,nvecs,m2)
            savenames = []
            for vec in range(nvecs+1):
                savenames.append('./{0}/empca/{1}empcaeig{2}_order{3}_seed{4}_cross{5}_nvec{6}.png'.format(model.type,subgroup,vec, model.order,model.seed,model.cross,nvecs))
            labels = ['Unweighted EMPCA - raw','Weighted EMPCA - raw','Unweighted EMPCA - proc','Weighted EMPCA - proc']
            eigvecs = [newm1,newm2,m3.eigvec,m4.eigvec]
            plot_element_eigvec(eigvecs,savenames,labels=labels,hidefigs=hide)

    elif model.subgroups[0] == False:
        
        empcaname = model.outName('pkl',content = 'empca',order = model.order,seed = model.seed,cross=model.cross)
        empcaname = empcaname.split('.pkl')[0]+'_nvec{0}'.format(nvecs)+'.pkl'
        m1,m2,w1 = pix_empca(model,model.residual,model.errs,empcaname,nvecs=nvecs,gen=gen,verbose=verbose,nstars=nstars,deltR2=deltR2,usemad=usemad)
        
        residual,errs = weight_residual(model,model.numstars,plot=True)
        empcaname = model.outName('pkl',content = 'empca_element',order = model.order,
                                       seed = model.seed,cross=model.cross)
        empcaname = empcaname.split('.pkl')[0]+'_nvec{0}'.format(nvecs)+'.pkl'
        m3,m4,w2 = elem_empca(model,residual,errs,empcaname,nvecs=14,gen=gen,verbose=verbose,deltR2=deltR2,usemad=usemad)
        
        labels = ['Unweighted EMPCA - raw','Weighted EMPCA - raw']
        savename = './{0}/empca/pix_empcaR2_order{1}_seed{2}_cross{3}_{4}_u{5}_d{6}_nvec{7}_MAD{8}.png'.format(model.type,model.order,model.seed,model.cross,model.label,model.up,model.low,nvecs,usemad)
        ptitle = 'R2 from pixel space'
        plot_R2([m1,m2],w1,ptitle,savename,labels=None,nvecs=nvecs,usemad=usemad,hide=hide)
        labels = ['Unweighted EMPCA - proc','Weighted EMPCA - proc']
        savename = './{0}/empca/elem_empcaR2_order{1}_seed{2}_cross{3}_{4}_u{5}_d{6}_nvec{7}_MAD{8}.png'.format(model.type,model.order,model.seed,model.cross,model.label,model.up,model.low,nvecs,usemad)
        ptitle = 'R2 from element space'
        plot_R2([m3,m4],w2,ptitle,savename,labels=None,nvecs=len(elems)-1,usemad=usemad,hide=hide)

        resize_pix_eigvecs(model.residual,m1,nstars=nstars)
        resize_pix_eigvecs(model.residual,m2,nstars=nstars)

        newm1 = weight_eigvec(model,nvecs,m1)
        newm2 = weight_eigvec(model,nvecs,m2)
        savenames = []
        for vec in range(nvecs+1):
            savenames.append('./{0}/empca/empcaeig{1}_order{2}_seed{3}_cross{4}_{5}_u{6}_d{7}_nvec{8}.png'.format(model.type,vec,model.order,model.seed,model.cross,model.label,model.up,model.low,vec))
        labels = ['Unweighted EMPCA - raw','Weighted EMPCA - raw','Unweighted EMPCA - proc','Weighted EMPCA - proc']
        eigvecs = [newm1,newm2,m3.eigvec,m4.eigvec]
        plot_element_eigvec(eigvecs,savenames,labels=labels,hidefigs=hide,nvecs=len(elems)-1)

    if not hide:
        plt.show()







