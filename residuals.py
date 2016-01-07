# Import base packages
import numpy as np
import os
from warnings import warn

# Import plotting packages
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# Import APOGEE/sample packages
import apogee.tools.read as apread
from apogee.tools import bitmask
import window as wn
from read_clusterdata import read_caldata

# Import fitting and analysis packages
import access_spectrum as acs
import reduce_dataset as rd
import polyfit as pf


# Dictionary to translate APOGEE's pixel mask (DR12).
# Keys correspond to set bits in the mask.

APOGEE_PIXMASK={0:"BADPIX", # Pixel marked as BAD in bad pixel mask
                1:"CRPIX", # Pixel marked as cosmic ray in ap3d
                2:"SATPIX", # Pixel marked as saturated in ap3d
                3:"UNFIXABLE", # Pixel marked as unfixable in ap3d
                4:"BADDARK", # Pixel marked as bad as determined from dark frame
                5:"BADFLAT", # Pixel marked as bad as determined from flat frame
                6:"BADERR", # Pixel set to have very high error (not used)
                7:"NOSKY", # No sky available for this pixel from sky fibers
                8:"LITTROW_GHOST", # Pixel falls in Littrow ghost, may be affected
                9:"PERSIST_HIGH", # Pixel falls in high persistence region, may be affected
                10:"PERSIST_MED", # Pixel falls in medium persistence region, may be affected
                11:"PERSIST_LOW", # Pixel falls in low persistence region, may be affected
                12:"SIG_SKYLINE", # Pixel falls near sky line that has significant flux compared with object
                13:"SIG_TELLURIC", # Pixel falls near telluric line that has significant absorption
                14:"NOT_ENOUGH_PSF", # Less than 50 percent PSF in good pixels
                15:"POORSNR", # Signal to noise below limit
                16:"FAILFIT" # Fitting for stellar parameters failed on pixel
                } 

# Chosen set of bits on which to mask
badcombpixmask= bitmask.badpixmask()+2**bitmask.apogee_pixmask_int("SIG_SKYLINE")

# Elements APOGEE fits for
elems = ['Al','Ca','C','Fe','K','Mg','Mn','Na','Ni','N','O','Si','S','Ti','V']

# Output directories for different file types
outdirs = {'pkl':'pickles/',		# Directory to store data in pickled format
		   'fit':'fitplots/',		# Directory to store plots from fitting for variables in fitvars
		   'res':'residual_plots/'	# Directory to store plots of residuals from fits 
		   }

outfile = {'pkl':'.pkl',
		   'fit':'.png',
		   'res':'.png'
		   }

# Functions to access particular sample types
readfn = {'clusters' : read_caldata,		# Sample of open and globular clusters
		  'OCs': read_caldata,				# Sample of open clusters
		  'GCs': read_caldata,				# Sample of globular clusters
		  'red_clump' : apread.rcsample		# Sample of red clump stars
		  }

# Stellar properties to fit for different sample types
fitvars = {'clusters':['TEFF'],					# Fit clusters in effective temperature
		   'OCs':['TEFF'],						# Fit open clusters in effective temperature
		   'GCs':['TEFF'],						# Fit globular clusters in effective temperature
		   'red_clump':['TEFF','LOGG','FE_H']	# Fit red clump stars in effective temperature, surface gravity and iron abundance
		   }

# Transparency properties for outdirs['fit'] plots.  
alphas = {'clusters':1,	 
		   'OCs':1,
		   'GCs':1,
		   'red_clump':0.5
		   }

#**************************************
aspcappix = 7214

def retryPixFunction(fn,dependencies,*args,**kwargs):
	"""
	Tries to run a function. If it fails the first attempt, loads dependencies and tries again.

	fn:				Function to run (is passed *args)
	dependencies:	Functions fn requires to have run first (are passed **kwargs).

	Returns nothing.

	"""
	try:
		return fn(*args)
	except AttributeError as e:
		for dep in dependencies:
			dep(**kwargs)
		try:
			return fn(*args)
		except AttributeError as e:
			print e
			warn('Missing Sample information')

windowinfo = 'windowinfo.pkl'
def readElementWindow(fname):
	"""
	Retrieves information about which pixels correspond to particular element windows.

	fname:		Name of file in which window information is stored.

	Returns four objects:
		elemwindows:		Dictionary of pixel windows corresponding to each element.
		windowPixels:		Dictionary of pixels where windows are non zero for each element.
		tophats:			Dictionary of tophats for the windows for each element.
		window_all:			An array containing windows for each element stacked.	

	"""
	if not os.path.isfile(fname):
		window_all = np.zeros(aspcappix)
		window_peak = np.zeros(aspcappix)
		windowPeaks = {}
		elemwindows = {}
		windowPixels = {}
		tophats = {}
		for elem in elems:
			# Read in window function for elem from Data Release 12 information and use the ASCAP pixel grid.
			w = wn.read(elem,dr = 12,apStarWavegrid = False)
			elemwindows[elem] = w
			windowPixels[elem] = np.where(w != 0)
			tophats[elem] = wn.tophat(elem,dr=12,apStarWavegrid=False)
			window_all += w
			# Find peaks
			firstDeriv = np.roll(w,1) - w
			secondDeriv = np.roll(firstDeriv,1)-firstDeriv
			peaks = (np.where(secondDeriv < 0)[0]-1,)
			window_peak[peaks] = 1
			windowPeaks[elem] = peaks
		acs.pklwrite(fname,[elemwindows,window_all,window_peak,windowPeaks,windowPixels,tophats])
	elif os.path.isfile(fname):
		elemwindows,window_all,window_peak,windowPeaks,windowPixels,tophats = acs.pklread(fname)
	return elemwindows,window_all,window_peak,windowPeaks,windowPixels,tophats

elemwindows,window_all,window_peak,windowPeaks,windowPixels,tophats = readElementWindow(windowinfo)

def getSpectra(data,fname,ind,readtype='asp',gen=False):
	"""
	A sample-type independent function to retrieve spectra of the processed ('asp'),
	or unprocessed ('ap') type.

	data:		Dictionary containing APOGEE retrieval information ('LOCATION_ID' and 'APOGEE_ID' keys).
	fname:		File in which to save spectra.
	ind:		Index of the extension to retrieve.
	readtype:	Set to processed 'asp' or unprocessed 'ap' type.
	gen:		Boolean. If True, reload spectra even if fname exists.

	Returns an array of spectra.

	"""
	if os.path.isfile(fname) and not gen:
		return acs.pklread(fname)
	elif not os.path.isfile(fname) or gen:
		if readtype == 'asp':
			spectra = acs.get_spectra_asp(data,ext = ind)
		elif readtype == 'ap':
			spectra = acs.get_spectra_ap(data,ext = ind, indx = 1)
		else:
			print "Choose 'asp' or 'ap' as type."
		acs.pklwrite(fname,spectra)
		return spectra

def doubleResidualHistPlot(title,residual,sigma,savename,bins = 50,rangecut = 0.1):
	"""
	Plots the histogram of flux uncertainties superimposed over the histogram of residuals.

	title:		Title of the plot.
	residual:	Array of residuals with which to find the histogram.
	sigma:		Array of flux uncertainties with which to find histogram
	savename:	Location to save plot.
	bins:		Optional integer kwarg specifying the number of bins in the histogram. (Default = 50)
	rangecut:	Optional float kwarg specifying the bounds of the histogram. (Default = 0.1)

	Returns nothing, saves the plot.
	"""
	plt.figure(figsize = (12,10))
	Rhist,Rbins = np.histogram(residual,bins = bins,range = (-rangecut,rangecut))
	Ghist,Gbins = np.histogram(sigma,bins = bins,range = (-rangecut,rangecut))
	plt.bar(Rbins[:-1],Rhist/float(max(Rhist)),width = (Rbins[1]-Rbins[0]))
	plt.bar(Gbins[:-1],Ghist/float(max(Ghist)),width = (Gbins[1]-Gbins[0]),color = 'g',alpha = 0.75)
	plt.xlim(-rangecut,rangecut)
	plt.xlabel('Weighted scatter')
	plt.ylabel('Star count normalized to peak')
	plt.title(title)
	plt.savefig(savename)
	plt.close()

class Sample:
	"""
	A class object to hold information about a sample of stellar spectra, including properties of their fits in stellar parameters.

	"""
	def __init__(self,sampletype,seed=1,order=2,label=0,low=0,up=0,cross=True,fontsize=18,verbose=False):
		"""
		Initializes appropriate variables for sample class.

		sampletype:		String that specifies the type of stellar spectra to be used. Current options are: 'clusters', 'red_clump','OCs','GCs'.
		seed:			Integer used to initialize random seed for error estimation. 
		order:			Integer that specifies the order of the polynomial to use in fitting routines.
		label:			Optional kwarg that may be used to specify a stellar parameter in which to select part of the sample. Default is zero,
						in which case the whole sample is considered.
		low:			Optional kwarg that sets the lower limit of value in label that will be accepted as part of the sample.	Considered only if
						label is nonzero.
		up:				Optional kwarg that sets the upper limit of value in label that will be accepted as part of the sample.	Considered only if
						label is nonzero.	
		cross:			Optional kwarg that sets whether the polynomial fits include cross terms. Default is True (include cross terms).
						May be False for no cross terms or a tuple of sets of indices matching the independent variable tuple indices 
						to specify which variable cross terms are to be used. See fitvars dictionary for the order of independent variables.
		fontsize:		Optional kwarg that sets fontsize in all plots. Default is 18.
		verbose:		Optional Boolean kwarg. If True, prints warnings and progress updates. Default is False.

		Returns Sample class object with input variables, derived file names and data set as part of the object.		

		"""

		self.verbose = verbose

		self.type = sampletype		
		self.overdir = './'+sampletype+'/'
		self.label = label
		self.low = low
		self.up = up
		if self.label != 0 and abs(self.low - self.up) < 1e-5:
			if verbose:
				warn('kwarg label was set, but limits are too close - reverting to use of entire sample.')
			self.label = 0

		# Create directories if necessary and initialize file paths.
		self.makeDirec()

		# Retrieve data set
		self.getData()

		# Initialize mask
		if os.path.isfile(self.maskname):
			self.mask = acs.pklread(self.maskname)
			self.updatemask = False
			if self.verbose:
				print 'Mask loaded from file.'
		elif not os.path.isfile(self.maskname):
			self.mask = np.zeros(self.specs.shape).astype(bool)
			self.updatemask = True

		self.specs = np.ma.masked_array(self.specs,self.mask)
		self.errs = np.ma.masked_array(self.errs,self.mask)

		self.numstars = len(self.specs)
		
		self.seed = seed
		np.random.seed(seed)
		
		self.order = order
		self.cross = cross
		

		font = {'family' : 'serif',
        		'weight' : 'normal',
        		'size'   : fontsize}
		matplotlib.rc('font', **font)


	def outName(self,filetype,content = '',subgroup = False,order = False,elem = False,pixel = False,seed = False,cross=False):
		"""
		A function to generate output file names.

		filetype:	A keyword to specify file destination and file extension (options are 'pkl','res', and 'fit').
		content:	A string kwarg describing the general contents of the file. Default is ''.
		subgroup:	If not False, a string kwarg describing the stellar grouping to which this data belongs. Default False.
		order:		If not False, an integer kwarg denoting the order of the fit represented in the data. Default False.
		elem:		If not False, a string kwarg denoting the atomic element to which this data belongs. Default False.
		pixel:		If not False, an integer kwarg denoting the pixel at which the data was taken. Default False.
		seed:		If not False, an integer kwarg chosen to initialize random seed. Default False.
		cross:		If not False, denotes the cross terms were used in the fit. Default False.

		Returns a filepath.

		"""
		prefix = ''
		if subgroup != False:
			prefix += subgroup+'_'
		if elem != False:
			prefix += elem+'_'
		if pixel != False:
			prefix += 'pix'+str(pixel)+'fit_'
		if order != False:
			prefix += 'order'+str(order)+'_'
		if cross != False:
			if cross == True:
				prefix += 'allcross_'
			elif isinstance(cross,tuple):
				prefix += 'cross'
				for iset in cross:
					prefix += '['
					for ind in iset:
						prefix += fitvars[ind]+','
					prefix += ']'
		if seed != False:
			prefix += 'seed'+str(seed)+'_'

		# If data set was cropped, incorporate this in the file name.
		if self.label != 0:
			return self.overdir+outdirs[filetype]+prefix+content+'_{0}_u{1}_d{2}'.format(self.label,self.up,self.low)+outfile[filetype]
		elif self.label == 0:
			return self.overdir+outdirs[filetype]+prefix+content+outfile[filetype]

	def makeDirec(self):
		"""
		Creates output directories if necessary.

		Updates Sample class object with file paths.
		"""

		# Check for output directory existence and create them if necessary.
		if not os.path.isdir(self.overdir):
			os.system('mkdir '+self.overdir)
		for outdir in outdirs.values():
			if not os.path.isdir(self.overdir+outdir):
				os.system('mkdir '+self.overdir+outdir)

		# Set file paths.
		ftype = 'pkl'
		self.specname = self.outName(ftype,'spectra')
		self.errname = self.outName(ftype,'errs')
		self.maskname = self.outName(ftype,'mask')
		self.bitmaskname = self.outName(ftype,'bitmask')

	def getData(self):
		"""
		Updates Sample class object with data set information, stellar spectra, flux uncertainties and bitmask information.
		"""
		# Read in data set information dictionary with appropriate function
		self.data = readfn[self.type]()
		
		# If necessary, crop the data set.
		if self.label != 0:
			sindx = rd.slice_data(self.data,[self.label,self.low,self.up])
			self.data = self.data[sindx]
		if self.type == 'OCs':
			sindx = np.where(self.data['CLUSTER'] in OCs)
			self.data = self.data[sindx]
		if self.type == 'GCs':
			sindx = np.where(self.data['CLUSTER'] in GCs)
			self.data = self.data[sindx]

		# Reset dictionary keys
		if self.type == 'OCs' or self.type == 'GCs' or self.type == 'clusters':
			self.data['APOGEE_ID'] = self.data['ID']

		# Retrieve stellar spectra as array	
		self.specs = getSpectra(self.data,self.specname,1,'asp')

		# If spectra returned as tuple, cut identified bad indices out of the data set.
		if isinstance(self.specs,tuple):
			self.data = self.data[self.specs[1]]
			self.specs = self.specs[0][self.specs[1]]

		# Retrieve pixel flux uncertainties and bitmasks with new cropped data set.
		self.errs = getSpectra(self.data,self.errname,2,'asp')
		self.bitmask = getSpectra(self.data,self.bitmaskname,3,'ap')
		# Convert bitmask to larger integer (from np.int16)
		self.bitmask = self.bitmask.astype(np.int64())


	def snrCorrect(self,cutoff = 200.):
		"""
		Corrects signal to noise ratio when it appears to have been underestimated by increasing the noise estimate.

		cutoff:		Upper limit for signal to noise ratio

		Updates pixel flux uncertainty in Sample object.
		"""
		SNR = self.specs/self.errs
		toogood = np.where(SNR > cutoff)
		self.errs[toogood] = self.specs[toogood]/cutoff

	def snrCut(self,cutoff = 50.):
		"""
		Masks pixels where the signal to noise ratio is too low.

		cutoff: 	Lower limit for signal to noise ratio

		Updates the mask and bitmask.
		"""
		if self.updatemask:
			SNR = self.specs/self.errs
			toobad = np.where(SNR < cutoff)
			self.mask[toobad] = True 
			self.bitmask[toobad] += 2**15 # Set bit 15 in bitmask
			self.specs.mask = self.mask
			self.errs.mask = self.mask

	def bitmaskData(self,maskbits = 'all'):
		"""
		Use bitmask to create masked array for spectra and pixel flux uncertainties.

		maskbits:	If not 'all', must be a list of bits to mask on. Default: 'all'.

		Updates the mask, spectra and pixel flux uncertainties.
		"""
		if self.updatemask:
			if isinstance(maskbits,(list,np.ndarray)):
				for m in maskbits:
					bitind = bitmask.bit_set(m,np.copy(self.bitmask))
					self.mask[bitind] = True
			elif isinstance(maskbits,(float,int)):
				maskbits = bitmask.bits_set(maskbits)
				for m in maskbits:
					bitind = bitmask.bit_set(m,np.copy(self.bitmask))
					self.mask[bitind] = True
			elif maskbits != 'all':
				warn('Invalid format for selection bits to mask on. Masking where any bit is set.')
				maskbits = 'all'
			elif maskbits == 'all':
				maskregions = np.where((self.bitmask != 0))
				self.mask[maskregions] = True
			self.specs.mask = self.mask
			self.errs.mask = self.mask


	def saveFiles(self): #********************* a general save updated files?
		acs.pklwrite(self.maskname,self.mask)
		acs.pklwrite(self.bitmaskname,self.bitmask)
		acs.pklwrite(self.specname,self.specs)
		acs.pklwrite(self.errname,self.errs)

################################################################################
######################## MASK INDEPENDENT VARIABLES ############################

	def indepVars(self,pix):
		"""
		Create tuple of independent variable arrays masked according to the given pixel.

		pix:	Integer specifying pixel whose mask to use.

		Returns a tuple of masked independent variable arrays.
		"""
		indeps = ()
		for fvar in fitvars[self.type]:
			indeps += (np.ma.masked_array(self.data[fvar],self.specs[:,pix].mask),)
		return indeps

	def allIndepVars(self,subgroup=False):
		"""
		Create a list of masked independent variable array tuples corresponding to each pixel.

		subgroup:	If not False, a string kwarg describing the stellar grouping to which this data belongs. Default False.

		Returns nothing, updates Sample.allindeps and writes it to file.
		"""
		fname = self.outName('pkl',content='indeps',subgroup=subgroup)
		if os.path.isfile(fname):
			self.allindeps = acs.pklread(fname)
		elif not os.path.isfile(fname):
			self.allindeps = []
			for pix in range(aspcappix):
				indeps = self.indepVars(pix)
				self.allindeps.append(indeps)
			acs.pklwrite(fname,self.allindeps)

################################################################################
############################## FIT ALONG PIXEL #################################

	def pixFit(self,pix):
		"""
		Fits a data set in independent variables specified in fitvars at a particular pixel and calculates residuals from the fit.

		pix:		Integer specifying pixel at which to perform fit.
		indeps:		Tuple of indenpendent variable arrays.

		Returns an array of fit parameters and a list identifying which variables belong to each parameter.
		"""
		indeps = self.allindeps[pix]
		
		if self.cross != False and len(indeps) == 1:
			if self.verbose:
				warn('Cross terms were requested, but fit is in a single variable.')
		
		# Exception handling for possible linear algebra errors that may arise from the fit (non invertible matrices etc.)
		try:
			# Construct independent variable matrix and provide a dictionary identifying the columns with combinations of variables.
			indepMatrix,colcode = pf.makematrix(indeps,self.order,cross=self.cross)
			# Create matrix of uncertainty in flux for each star (assumes stars are uncorrelated)
			uncert = np.diag(self.errs[:,pix]**2)

			# Check for potential degeneracy between terms, which leads to poor determination of fit parameters.
			imat = np.matrix(indepMatrix)
			eigvals,eigvecs = np.linalg.eig(imat.T*np.linalg.inv(uncert)*imat)	
			if any(abs(eigvals) < 1e-10):
				warn('With cross terms, there is too much degeneracy between terms. Reverting to no cross terms used for fit pix {0}'.format(pix))
				indepMatrix,colcode = pf.makematrix(indeps,self.order,cross=False)

			uncert = np.diag(self.errs[:,pix].data[self.errs[:,pix].mask==False]**2)
			# Attempt to calculate the fit parameters and determine if there are enough data points to trust results.
			fitParam = pf.regfit(indepMatrix,colcode,self.specs[:,pix],C = uncert,order = self.order)
			if (self.numstars-np.sum(self.specs[:,pix].mask)) <= len(fitParam) + 1:
				raise np.linalg.linalg.LinAlgError('Data set too small to determine fit coefficients')
		
		# If exception raised, mask pixel for all stars.
		except np.linalg.linalg.LinAlgError as e:
			fitParam = np.zeros(self.order*len(indeps)+1)
			self.specs.mask[:,pix] = np.ones(self.numstars).astype(bool)
			self.errs.mask[:,pix] = np.ones(self.numstars).astype(bool)
			if self.verbose:
				print e
			if self.updatemask:
				self.mask[:,pix] = True
				self.bitmask[:,pix] += 2**16
				if self.verbose:
					'Mask on pixel {0}'.format(pix)

		return fitParam,colcode

	def allPixFit(self,subgroup=False):
		"""
		Calculates polynomial fits at each pixel.

		subgroup:	If not False, a string kwarg describing the stellar grouping to which this data belongs. Default False.

		Returns nothing, updates Sample.allparams, Sample.allcodes and saves them both to file.
		"""
		fname1 = self.outName('pkl',content='fitparam',order=self.order,subgroup=subgroup)
		fname2 = self.outName('pkl',content='colcodes',order=self.order,subgroup=subgroup)
		if not os.path.isfile(fname1) or not os.path.isfile(fname2):
			self.allparams = []
			self.allcodes = []
			for pix in range(aspcappix):
				param,colcode = retryPixFunction(self.pixFit,[self.allIndepVars],pix,subgroup=subgroup)
				self.allparams.append(param)
				self.allcodes.append(colcode)
			acs.pklwrite(fname1,self.allparams)
			acs.pklwrite(fname2,self.allcodes)
		elif os.path.isfile(fname1) and os.path.isfile(fname2):
			self.allparams = acs.pklread(fname1)
			self.allcodes = acs.pklread(fname2)

	
################################################################################
########################### CALCULATE FIT RESIDUALS ############################

	def pixResidiual(self,pix):
		"""
		Generates fit residuals at a pixel.

		pix:	 	Integer pixel at which to calculate residuals.

		Returns residuals of fit.
		"""
		indeps = self.allindeps[pix]
		params = self.allparams[pix]
		colcode = self.allcodes[pix]
		res = self.specs[:,pix] - pf.poly(params,colcode,indeps,order=self.order)
		return res


	def allPixResiduals(self,subgroup=False):
		"""
		Calculates residuals of the fit at each pixel.

		subgroup:	If not False, a string kwarg describing the stellar grouping to which this data belongs. Default False.

		Returns nothing, updates Sample.residual and saves it.
		"""
		fname = self.outName('pkl',content='residuals',order=self.order,subgroup=subgroup)
		if os.path.isfile(fname):
			self.residual = acs.pklread(fname)
		elif not os.path.isfile(fname):
			self.residual = []
			for pix in range(aspcappix):
				res = retryPixFunction(self.pixResidiual,[self.allPixFit],pix,subgroup=subgroup)
				self.residual.append(res)
			self.residual = np.ma.masked_array(self.residual)
			acs.pklwrite(fname,self.residual)

################################################################################
################################ PLOT RESIDUALS ################################

	def pixPlot(self,pix,savename,errcut = 0.1):
		"""
		Creates a plot of fit residuals for a specified pixel.

		pix: 		Pixel at which to plot fit residuals.
		indeps:		Tuple of independent variable arrays.
		inames:		Names of independent variables in order of indeps.
		savename:	Name of file to save plot.
		self:		self class object.
		errcut:		Cutoff on flux uncertainty to mark stars in red (kwarg, default = 0.1)

		Returns nothing, saves the plot.
		"""

		# Extract residuals and pixel uncertainties for given pixel.
		indeps = self.allindeps[pix]
		res = self.residual[pix]
		errs = self.errs[:,pix]
		# Find masked and unmasked stars.
		nomask = np.where((res.mask==0))
		mask = np.where(res.mask!=0)
		# Find indices to plot in red (rpl) or blue (bpl) based on error cutoff.
		rpl = np.where((errs[nomask] > errcut))
		bpl = np.where((errs[nomask] < errcut))

		inames = fitvars[self.type]
		plt.figure(figsize = (16,14))
		# Plot residuals vs each independent variable.
		for loc in range(len(indeps)):
			plt.subplot2grid((1,len(indeps)+1),(0,loc))
			# Plot masked values in magenta.
			plt.plot(indeps[loc].data[mask],res.data[mask],'.',color='magenta',alpha = alphas[self.type],label = 'Masked values')
			# Plot unmasked values with high uncertainty in red.
			plt.plot(indeps[loc].data[nomask][rpl],res.data[nomask][rpl],'.',color='red',label = 'Uncertainty > {0}'.format(errcut))
			# Plot unmasked values with low uncertainty in blue.
			plt.plot(indeps[loc].data[nomask][bpl],res.data[nomask][bpl],'.',color='blue',alpha=alphas[self.type],label = 'Uncertainty < {0}'.format(errcut))
			plt.ylim(-0.1,0.1)
			plt.xlabel(inames[loc])
			# If this is the first plot in the row, print a ylabel and a legend.
			if loc == 0:
				plt.ylabel('Fit residuals')
				plt.legend(loc = 'best')

		# Plot the residuals vs pixel flux uncertainty.
		plt.subplot2grid((1,len(indeps)+1),(0,len(indeps)))
		# Plot masked values in magenta.
		plt.semilogx(errs.data[mask],res.data[mask],'.',color='magenta',alpha = alphas[self.type])
		# Plot unmasked values with high uncertainty in red.
		plt.semilogx(errs.data[nomask][rpl],res.data[nomask][rpl],'.',color = 'red')
		# Plot unmasked values with low uncertainty in blue.
		plt.semilogx(errs.data[nomask][bpl],res.data[nomask][bpl],'.',color = 'blue',alpha = alphas[self.type])
		plt.ylim(-0.1,0.1)
		# Count the number of stars outside the plot range and note the quantity on the plot.
		outsidelims = abs(res) > 0.1
		numoutside = np.sum(outsidelims.astype(int))
		if numoutside > 0:
			plt.text((np.max(errs) - np.min(errs))/2.,0.09,'{0} outside range'.format(numoutside))
		plt.xlabel('Uncertainty in Pixel {0}'.format(pix))

		# Identify whether the pixel belongs to an absorption feature, and if so which element.
		try:
			ws = [item for item in windowPixels.values() if pix in item[0]][0]
			elem = [item for item in windowPixels.keys() if ws == windowPixels[item]][0]
			plt.suptitle(elem+' Pixel')
		except IndexError:
			plt.suptitle('Unassociated Pixel')
		plt.savefig(savename)
		plt.close()


	def setPixPlot(self,subgroup=False,whichplot='auto_narrow'):
		"""
		Automatically plots a subset of pixel fits.

		subgroup:	If not False, a string kwarg describing the stellar grouping to which this data belongs. Default False.	
		whichplot:	Identifies pixels to plot. May be keywords 'auto_broad','auto_narrow', 'all' or an element identifier. May also be a list of pixels to plot. Default 'auto_narrow'.
					'auto_broad': plots all pixels identified as part of any element's window function.
					'auto_narrow': plots all pixels identified as a peak of any elements window function.
					'all': plots all pixels.

		Returns nothing, but generates plots in outdirs['fits'].
		"""
		if whichplot == 'auto_broad':
			for pix in np.where(window_all != 0)[0]:
				plotname = self.outName('fit',pixel=pix,subgroup=subgroup,order=self.order,cross=self.cross)
				retryPixFunction(self.pixPlot,[self.allPixResiduals],pix,plotname,subgroup=subgroup)
		elif whichplot == 'auto_narrow':
			for pix in np.where(window_peak != 0)[0]:
				plotname = self.outName('fit',pixel=pix,subgroup=subgroup,order=self.order,cross=self.cross) 
				retryPixFunction(self.pixPlot,[self.allPixResiduals],pix,plotname,subgroup=subgroup)
		elif whichplot == 'all':
			for pix in range(aspcappix):
				plotname = self.outName('fit',pixel=pix,subgroup=subgroup,order=self.order,cross=self.cross) 
				retryPixFunction(self.pixPlot,[self.allPixResiduals],pix,plotname,subgroup=subgroup)
		elif whichplot in windowPixels.keys():
			for pix in windowPixels[whichplot]:
				plotname = self.outName('fit',pixel=pix,subgroup=subgroup,order=self.order,cross=self.cross) 
				retryPixFunction(self.pixPlot,[self.allPixResiduals],pix,plotname,subgroup=subgroup)
		elif isinstance(whichplot,(list,np.ndarray)):
			for pix in whichplot:
				plotname = self.outName('fit',pixel=pix,subgroup=subgroup,order=self.order,cross=self.cross) 
				retryPixFunction(self.pixPlot,[self.allPixResiduals],pix,plotname,subgroup=subgroup)
		else:
			warn('Unrecognized option choice for kwarg whichplot, please use "auto_narrow", "auto_broad" or "all", or provide a list of pixels to plot.')

################################################################################
################################# ESTIMATE UNCERTAINTY #########################


	def randomSigma(self,pix):
		"""
		Generates an uncertainty for each star by selecting randomly from a Gaussian with 
		the standard deviation of the provided uncertainty.

		pix:	Pixel at which to find uncertainties.

		Returns an array of uncertainties corresponding to each star at pixel pix.
		"""

		sigma = np.ma.masked_array([-1]*(len(self.specs[:,pix])),mask = self.mask[:,pix],dtype = np.float64)
		for s in range(len(sigma)):
			if not sigma.mask[s]:
				sigma.data[s] = np.random.normal(loc = 0,scale = self.errs[:,pix][s])
		return sigma

	def allRandomSigma(self,subgroup=False):
		"""
		Generates an uncertainty at each pixel for each star by selecting randomly from a Gaussian with 
		the standard deviation of the provided uncertainty.

		subgroup: If not False, a string kwarg describing the stellar grouping to which this data belongs. Default False.	

		Returns nothing, just updates the sigma attribute of Sample.
		"""
		fname = self.outName('pkl',content='sigma',seed = self.seed,subgroup=subgroup,order=self.order)
		if os.path.isfile(fname):
			self.sigma = acs.pklread(fname)
		elif not os.path.isfile(fname):
			sigs = []
			for pix in range(aspcappix):
				sig = self.randomSigma(pix)
				sigs.append(sig)
			self.sigma = np.ma.masked_array(sigs)
			acs.pklwrite(fname,self.sigma)

################################################################################
############################### WEIGHT RESIDUALS ###############################

	def weighting(self,arr,elem,name):
		"""
		Sums an input array weighted by the window function of a given element.

		arr:		Input array of length of the element windows loaded in readElementWindow.
		elem:		Element whose window function is to be used.
		name:		Name of save file.

		Returns weighted sum.

		"""
		if os.path.isfile(name):
			return acs.pklread(name)
		elif not os.path.isfile(name):
			w = elemwindows[elem]
			# Normalize the weights.
			nw = np.ma.masked_array(pf.normweights(w))
			weighted = np.ma.masked_array([])
			# Sum unmasked pixels weighted by element window for each star.
			for star in range(self.numstars):
				weighted = np.append(weighted,np.ma.sum(nw*arr[:,star]))
			acs.pklwrite(name,weighted)
			return weighted






