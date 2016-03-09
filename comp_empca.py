"""

Usage:
comp_empca [-hvx] [-s SEARCHSTR]

Options:
    -h, --help
    -v, --verbose
    -x, --hidefigs                      Option to hide figures
    -s SEARCHSTR, --search SEARCHSTR    String to search for files to compare [default: None]
"""

import os
import docopt
import access_spectrum as acs
from run_empca import R2,R2noise
import numpy as np
import matplotlib.pyplot as plt

def gen_colours(n,cmap = 'Spectral'):
    """
    Generate a list of colours of length n from a given colourmap
    
    n:      Number of colours.
    cmap:   Matplotlib colourmap name.
    """
    return plt.get_cmap(cmap)(np.linspace(0, 1.0, n))

def read_files(searchstr):
    """
    Given a list of search terms, search for files matching the list elements joined by '*' and return their contents.

    searchstr:   List of search terms
    
    Returns file contents and the list of files

    """
    searchstr = '*'.join(searchstr)
    os.system('ls {0} > filelist.txt'.format(searchstr))
    filelist = np.loadtxt('filelist.txt',dtype=str)
    models = []
    for f in filelist:
        models.append(acs.pklread(f))
    return models,filelist


if __name__=='__main__':

    # Read in command line arguments
    arguments = docopt.docopt(__doc__)

    verbose = arguments['--verbose']
    hide = arguments['--hidefigs']
    search = arguments['--search']
    search = search.split(',')

    models,filelist = read_files(search)

    pixinds = [i for i in range(len(filelist)) if 'elem' not in filelist[i]]
    pixinds_nomad = [i for i in pixinds if 'MADTrue' not in filelist[i]]
    pixinds_mad = [i for i in pixinds if i not in pixinds_nomad]
    eleminds = [i for i in range(len(filelist)) if 'elem' in filelist[i]]
    eleminds_nomad = [i for i in eleminds if 'MADTrue' not in filelist[i]]
    eleminds_mad = [i for i in eleminds if i not in eleminds_nomad]
    

    pcolours = gen_colours(len(pixinds))

    plt.figure(1,figsize=(14,9))

    cind = 0
    sind = 0
    for p in pixinds_nomad:
        print 'file = ',filelist[p]
        label = ''
        mad = False
        if 'correct' in filelist[p]:
            correct = filelist[p].split('_')[-1]
            correct = correct.split('.pkl')[0]
            correct = correct.split('SNR')[1]
            correct = correct.split('correct')
            if correct[0] != '':
                correct = correct[0]
            elif correct[0] == '':
                correct = correct[1].split('ed+')[1]
            label += correct+'\n'
        if 'MADTrue' in filelist[p]:
            label += ' M.A.D.'+'\n'
            mad = True
        nvecs = len(models[p][0].eigvec)
        vec_vals = range(0,nvecs+1)
        R2vals1 = R2(models[p][0],usemad=mad)
        R2vals2 = R2(models[p][1],usemad=mad)
        R2n1,var1,vnoise1 = R2noise(models[p][2],models[p][0],usemad=mad) 
        R2n2,var2,vnoise2 = R2noise(models[p][3],models[p][1],usemad=mad) 
        plt.figure(1)
        plt.subplot2grid((2,len(pixinds_nomad)),(0,sind))
        plt.ylim(0,1)
        plt.xlim(0,nvecs)
        plt.ylabel('R2')
        plt.xlabel('Number of EMPCA vectors')
        plt.axhline(R2n1,linestyle='--',color = 'k')
        plt.fill_between(vec_vals,R2n1,1,color=pcolours[cind],alpha=0.2)
        plt.plot(vec_vals,R2vals1,marker='o',linewidth = 3,markersize=8,label=label+' unweighted',color = pcolours[cind])
        plt.legend(loc='best',fontsize=10,title='R2_noise = {0:2f}\n var = {1:2f}\n Vnoise = {2:2f}'.format(R2n1,var1,vnoise1))
        plt.subplot2grid((2,len(pixinds_nomad)),(1,sind))
        plt.ylim(0,1)
        plt.xlim(0,nvecs)
        plt.ylabel('R2')
        plt.xlabel('Number of EMPCA vectors')
        plt.axhline(R2n2,linestyle='--',color = 'k')
        plt.fill_between(vec_vals,R2n2,1,color=pcolours[cind+1],alpha=0.2)
        plt.plot(vec_vals,R2vals2,marker='o',linewidth = 3,markersize=8,label=label+' weighted',color = pcolours[cind+1])
        plt.legend(loc='best',fontsize=10,title='R2_noise = {0:2f}\n var = {1:2f}\n Vnoise = {2:2f}'.format(R2n2,var2,vnoise2))
        plt.suptitle('Pixel Space')
        sind+=1
        cind+=2

    cind = 0
    sind = 0

    plt.figure(2,figsize=(14,9))

    cind = 0
    sind = 0
    for p in pixinds_mad:
        print 'file = ',filelist[p]
        label = ''
        mad = False
        if 'correct' in filelist[p]:
            correct = filelist[p].split('_')[-1]
            correct = correct.split('.pkl')[0]
            correct = correct.split('SNR')[1]
            correct = correct.split('correct')
            if correct[0] != '':
                correct = correct[0]
            elif correct[0] == '':
                correct = correct[1].split('ed+')[1]
            label += correct+'\n'
        if 'MADTrue' in filelist[p]:
            label += ' M.A.D.'+'\n'
            mad = True
        nvecs = len(models[p][0].eigvec)
        vec_vals = range(0,nvecs+1)
        R2vals1 = R2(models[p][0],usemad=mad)
        R2vals2 = R2(models[p][1],usemad=mad)
        R2n1,var1,vnoise1 = R2noise(models[p][2],models[p][0],usemad=mad) 
        R2n2,var2,vnoise2 = R2noise(models[p][3],models[p][1],usemad=mad) 
        plt.figure(2)
        plt.subplot2grid((2,len(pixinds_mad)),(0,sind))
        plt.ylim(0,1)
        plt.xlim(0,nvecs)
        plt.ylabel('R2')
        plt.xlabel('Number of EMPCA vectors')
        plt.axhline(R2n1,linestyle='--',color = 'k')
        plt.fill_between(vec_vals,R2n1,1,color=pcolours[cind],alpha=0.2)
        plt.plot(vec_vals,R2vals1,marker='o',linewidth = 3,markersize=8,label=label+' unweighted',color = pcolours[cind])
        plt.legend(loc='best',fontsize=10,title='R2_noise = {0:2f}\n var = {1:2f}\n Vnoise = {2:2f}'.format(R2n1,var1,vnoise1))
        plt.subplot2grid((2,len(pixinds_mad)),(1,sind))
        plt.ylim(0,1)
        plt.xlim(0,nvecs)
        plt.ylabel('R2')
        plt.xlabel('Number of EMPCA vectors')
        plt.axhline(R2n2,linestyle='--',color = 'k')
        plt.fill_between(vec_vals,R2n2,1,color=pcolours[cind+1],alpha=0.2)
        plt.plot(vec_vals,R2vals2,marker='o',linewidth = 3,markersize=8,label=label+' weighted',color = pcolours[cind+1])
        plt.legend(loc='best',fontsize=10,title='R2_noise = {0:2f}\n var = {1:2f}\n Vnoise = {2:2f}'.format(R2n2,var2,vnoise2))
        plt.suptitle('Pixel Space - MAD')
        sind+=1
        cind+=2

    cind = 0
    sind = 0


    pcolours = gen_colours(len(eleminds))

    plt.figure(3,figsize=(14,9))

    for p in eleminds_nomad:
        print 'file = ',filelist[p]
        label = ''
        mad = False
        if 'correct' in filelist[p]:
            correct = filelist[p].split('_')[-1]
            correct = correct.split('.pkl')[0]
            correct = correct.split('SNR')[1]
            correct = correct.split('correct')[0]
            label += correct+'\n'
        if 'MADTrue' in filelist[p]:
            label += ' M.A.D.'+'\n'
            mad = True
        nvecs = len(models[p][0].eigvec)
        vec_vals = range(0,nvecs+1)
        R2vals1 = R2(models[p][0],usemad=mad)
        R2vals2 = R2(models[p][1],usemad=mad)
        R2n1,var1,vnoise1 = R2noise(models[p][2],models[p][0],usemad=mad) 
        R2n2,var2,vnoise2 = R2noise(models[p][3],models[p][1],usemad=mad) 
        plt.figure(3)
        plt.subplot2grid((2,len(eleminds_nomad)),(0,sind))
        plt.ylim(0,1)
        plt.xlim(0,nvecs)
        plt.ylabel('R2')
        plt.xlabel('Number of EMPCA vectors')
        plt.axhline(R2n1,linestyle='--',color = 'k')
        plt.fill_between(vec_vals,R2n1,1,color=pcolours[cind],alpha=0.2)
        plt.plot(vec_vals,R2vals1,marker='o',linewidth = 3,markersize=8,label=label+' unweighted',color = pcolours[cind])
        plt.legend(loc='best',fontsize=10,title='R2_noise = {0:2f}\n var = {1:2f}\n Vnoise = {2:2f}'.format(R2n1,var1,vnoise1))
        plt.subplot2grid((2,len(eleminds_nomad)),(1,sind))
        plt.ylim(0,1)
        plt.xlim(0,nvecs)
        plt.ylabel('R2')
        plt.xlabel('Number of EMPCA vectors')
        plt.axhline(R2n2,linestyle='--',color = 'k')
        plt.fill_between(vec_vals,R2n2,1,color=pcolours[cind+1],alpha=0.2)
        plt.plot(vec_vals,R2vals2,marker='o',linewidth = 3,markersize=8,label=label+' weighted',color = pcolours[cind+1])
        plt.legend(loc='best',fontsize=10,title='R2_noise = {0:2f}\n var = {1:2f}\n Vnoise = {2:2f}'.format(R2n2,var2,vnoise2))
        plt.suptitle('Element Space')
        sind+=1
        cind+=2
    plt.show()

    sind=0
    cind=0
    plt.figure(4,figsize=(14,9))

    for p in eleminds_mad:
        print 'file = ',filelist[p]
        label = ''
        mad = False
        if 'correct' in filelist[p]:
            correct = filelist[p].split('_')[-1]
            correct = correct.split('.pkl')[0]
            correct = correct.split('SNR')[1]
            correct = correct.split('correct')[0]
            label += correct+'\n'
        if 'MADTrue' in filelist[p]:
            label += ' M.A.D.'+'\n'
            mad = True
        nvecs = len(models[p][0].eigvec)
        vec_vals = range(0,nvecs+1)
        R2vals1 = R2(models[p][0],usemad=mad)
        R2vals2 = R2(models[p][1],usemad=mad)
        R2n1,var1,vnoise1 = R2noise(models[p][2],models[p][0],usemad=mad) 
        R2n2,var2,vnoise2 = R2noise(models[p][3],models[p][1],usemad=mad) 
        plt.figure(4)
        plt.subplot2grid((2,len(eleminds_mad)),(0,sind))
        plt.ylim(0,1)
        plt.xlim(0,nvecs)
        plt.ylabel('R2')
        plt.xlabel('Number of EMPCA vectors')
        plt.axhline(R2n1,linestyle='--',color = 'k')
        plt.fill_between(vec_vals,R2n1,1,color=pcolours[cind],alpha=0.2)
        plt.plot(vec_vals,R2vals1,marker='o',linewidth = 3,markersize=8,label=label+' unweighted',color = pcolours[cind])
        plt.legend(loc='best',fontsize=10,title='R2_noise = {0:2f}\n var = {1:2f}\n Vnoise = {2:2f}'.format(R2n1,var1,vnoise1))
        plt.subplot2grid((2,len(eleminds_mad)),(1,sind))
        plt.ylim(0,1)
        plt.xlim(0,nvecs)
        plt.ylabel('R2')
        plt.xlabel('Number of EMPCA vectors')
        plt.axhline(R2n2,linestyle='--',color = 'k')
        plt.fill_between(vec_vals,R2n2,1,color=pcolours[cind+1],alpha=0.2)
        plt.plot(vec_vals,R2vals2,marker='o',linewidth = 3,markersize=8,label=label+' weighted',color = pcolours[cind+1])
        plt.legend(loc='best',fontsize=10,title='R2_noise = {0:2f}\n var = {1:2f}\n Vnoise = {2:2f}'.format(R2n2,var2,vnoise2))
        plt.suptitle('Element Space - MAD')
        sind+=1
        cind+=2
    plt.show()

