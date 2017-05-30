from empca_residuals import *

bmask = 4351
datadir = '/geir_data/scr/price-jones/Data/apogee_dim_reduction/'
maxsamp = 5

redclump = empca_residuals('apogee','red_clump',maskFilter,ask=True,degree=2,badcombpixmask=bmask,datadir = datadir)

redclump.samplesplit(fullsamp=False,subsamples=25,maxsamp=maxsamp,varfuncs=[np.ma.var,meanMed])