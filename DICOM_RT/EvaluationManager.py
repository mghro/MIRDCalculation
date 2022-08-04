#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Nov  2 10:33:18 2021
Last modified on Tue Jan 18 14:47 2022

@author: Mislav Bobić and Alejandro Bertolet
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import csv
import DICOM_RT.DicomPatient
from scipy.interpolate import interp1d

class EvaluationManager:
    def __init__(self, dicomPat):
        self.patient = dicomPat
        self.structureArrays = dicomPat.structures3D
        self.ROINames = [i for i in self.structureArrays]
        self.extraQoIs = []
        for q in dicomPat.quantitiesOfInterest:
            if q.quantity == 'Dose':
                self.doseArray = q.array
                self.doseUnit = q.unit
            else:
                self.extraQoIs.append(q)
        self.maxDose = np.max(self.doseArray)
        self.CalculateDVHs()
        
    def CalculateDVHs(self, numBins=1000):
        self.DVHDataFrame = pd.DataFrame()
        self.maxDose = np.max(self.doseArray)
        if len(self.extraQoIs) > 0:
            self.QoiDVHDataFrames = []
            for q in self.extraQoIs:
                self.QoiDVHDataFrames.append(pd.DataFrame())
        for ROIName in self.ROINames:
            structureDose = self.GetStructureDose(ROIName)
            histRange = (0, round(self.maxDose))
            histBins  = round(self.maxDose) if numBins is None else numBins-1
            differentialDVH, doseValues = np.histogram(structureDose, histBins, histRange)
            cumulativeDVH = np.zeros(len(differentialDVH)+1)
            index = 0
            cumulativeVoxels = 0
            for i in differentialDVH[::-1]:
                cumulativeVoxels += i/2
                np.put(cumulativeDVH, index, cumulativeVoxels)
                cumulativeVoxels += i/2
                index += 1
            np.put(cumulativeDVH, index, cumulativeVoxels)
            cumulativeDVH = cumulativeDVH[::-1]/cumulativeVoxels
            self.DVHDataFrame[ROIName] = cumulativeDVH
            qValuesArray = []
            if len(self.extraQoIs) > 0:
                for iq, q in enumerate(self.extraQoIs):
                    structQ = q.array[self.structureArrays[ROIName]]
                    histR = (0, round(np.max(q.array)))
                    histB = round(np.max(q.array)) if numBins is None else numBins-1
                    diffDVH, qValues = np.histogram(structQ, histB, histR)
                    qValuesArray.append(qValues)
                    cumDVH = np.zeros(len(diffDVH)+1)
                    ind = 0
                    cumVoxls = 0
                    for j in diffDVH[::-1]:
                        cumVoxls += j/2
                        np.put(cumDVH, ind, cumVoxls)
                        cumVoxls += j/2
                        ind += 1
                    np.put(cumDVH, ind, cumVoxls)
                    cumDVH = cumDVH[::-1]/cumVoxls
                    self.QoiDVHDataFrames[iq][ROIName] = cumDVH
        self.DVHDataFrame.insert(len(self.DVHDataFrame.columns)-1, 'Dose', doseValues)
        if len(self.extraQoIs) > 0:
            for i, q in enumerate(self.extraQoIs):
                self.QoiDVHDataFrames[i].insert(len(self.QoiDVHDataFrames[i].columns)-1, q.quantity, qValuesArray[i])
        print('DVHs calculated.')

    def GetStructureDose(self, ROIName, quantity='Dose'):
        if quantity == 'Dose':
            return self.doseArray[self.structureArrays[ROIName]]
        else:
            for i, q in enumerate(self.extraQoIs):
                if q.quantity == quantity:
                    return q.array[self.structureArrays[ROIName]]
    
    def GetMeanDose(self, ROIName, quantity='Dose'):
        if quantity == 'Dose':
            return np.average(self.GetStructureDose(ROIName))
        else:
            for i, q in enumerate(self.extraQoIs):
                if q.quantity == quantity:
                    return np.average(self.GetStructureDose(ROIName, quantity))
    
    def GetMaxDose(self, ROIName, quantity='Dose'):
        if quantity == 'Dose':
            return np.max(self.GetStructureDose(ROIName))
        else:
            for i, q in enumerate(self.extraQoIs):
                if q.quantity == quantity:
                    return np.max(self.GetStructureDose(ROIName, quantity))
    
    def GetMinDose(self, ROIName, quantity='Dose'):
        if quantity == 'Dose':
            return np.min(self.GetStructureDose(ROIName))
        else:
            for i, q in enumerate(self.extraQoIs):
                if q.quantity == quantity:
                    return np.min(self.GetStructureDose(ROIName, quantity))

    def EvaluateV(self, dose, ROIName, quantity='Dose'):
        if quantity == 'Dose':
            DVHDose = self.DVHDataFrame[quantity]
            DVHVolume = self.DVHDataFrame[ROIName]
        else:
            for i, q in enumerate(self.extraQoIs):
                if q.quantity == quantity:
                    DVHDose = self.QoiDVHDataFrames[i][quantity]
                    DVHVolume = self.QoiDVHDataFrames[i][ROIName]
        f = interp1d(DVHDose, DVHVolume)
        return float(f(dose))

    def EvaluateD(self, volume, ROIName, quantity='Dose'):
        if quantity == 'Dose':
            DVHDose = self.DVHDataFrame['Dose']
            DVHVolume = self.DVHDataFrame[ROIName]
        else:
            for i, q in enumerate(self.extraQoIs):
                if q.quantity == quantity:
                    DVHDose = self.QoiDVHDataFrames[i][quantity]
                    DVHVolume = self.QoiDVHDataFrames[i][ROIName]
        f = interp1d(DVHVolume, DVHDose)
        return float(f(volume))
    
    def PlotDVHs(self, quantity = "Dose", path=None):
        fig = plt.figure(dpi=300)
        ax = fig.add_subplot(1,1,1)
        xAxis = None
        if quantity == "Dose":
            xAxis = self.DVHDataFrame['Dose']
            DVHDataFrame = self.DVHDataFrame
            unit = self.doseUnit
        else:
            for i, q in enumerate(self.QoiDVHDataFrames):
                if self.extraQoIs[i].quantity == quantity:
                    xAxis = q[quantity]
                    DVHDataFrame = q
                    unit = self.extraQoIs[i].unit
            if xAxis is None:
                print("Quantity " + quantity + " could not be found.")
                return
        for ROIName in self.ROINames:
            yAxis = DVHDataFrame[ROIName]*100
            ax.plot(xAxis, yAxis, label=ROIName, linewidth=1.5)
        ax.set_xlabel((quantity + '[{}]').format(unit))
        ax.set_ylabel('Volume [%]')
        plt.legend()
        plt.grid(alpha=0.7, ls='--')
        if path is not None:
            plt.savefig(path + "/" + quantity + ".png")
            print(path + quantity + ".png saved.")
        plt.show()
        return fig

    def printMainResults(self, quantity = 'Dose', path=None):
        headers = 'Structure,Mean ' + quantity + ',Max ' + quantity + ',Min ' + quantity + ',D50,D98,D95,D90,D10,D5,D2'
        lines = []
        for ROIName in self.ROINames:
            line = ROIName + ','
            line += str(self.GetMeanDose(ROIName, quantity)) + ','
            line += str(self.GetMaxDose(ROIName, quantity)) + ','
            line += str(self.GetMinDose(ROIName, quantity)) + ','
            line += str(self.EvaluateD(0.5, ROIName, quantity)) + ','
            line += str(self.EvaluateD(0.98, ROIName, quantity)) + ','
            line += str(self.EvaluateD(0.95, ROIName, quantity)) + ','
            line += str(self.EvaluateD(0.90, ROIName, quantity)) + ','
            line += str(self.EvaluateD(0.10, ROIName, quantity)) + ','
            line += str(self.EvaluateD(0.05, ROIName, quantity)) + ','
            line += str(self.EvaluateD(0.02, ROIName, quantity))
            lines.append(line)
        print(headers)
        for l in lines:
            print(l)
        if path is not None:
            f = open(path + quantity + '.csv', 'w+')
            f.write(headers)
            f.write('\n')
            for l in lines:
                f.write(l)
                f.write('\n')
            f.close()
        
    def SaveCSV(self, CSVPath):
        self.DVHDataFrame.to_csv(CSVPath)
        
    def LoadCSV(self, CSVPath):
        self.DVHDataFrame = pd.read_csv(CSVPath)
        
    def SaveVoxelByVoxelCSV(self, CSVPath):
        f = open(CSVPath, 'w')
        writer = csv.writer(f)
        for ROIName in self.ROINames:
            writer.writerow([ROIName])
            headers = ['VoxelID', 'Dose (' + self.doseUnit + ')']
            qrois = []
            for q in self.extraQoIs:
                headers.append(q.quantity + " (" + q.unit + " )")
                qrois.append(q.array[self.structureArrays[ROIName]])
            writer.writerow(headers)
            dose = self.doseArray[self.structureArrays[ROIName]]
            indexes = np.where(self.structureArrays[ROIName])
            shape = self.structureArrays[ROIName].shape
            inds = []
            for i, ind in enumerate(indexes[0]):
                inds.append(indexes[0][i]*shape[1]*shape[2]+indexes[1][i]*shape[2] + indexes[2][i])
            for i, ind in enumerate(inds):
                row = []
                row.append(ind)
                row.append(dose[i])
                for qroi in qrois:
                    row.append(qroi[i])
                writer.writerow(row)
        f.close()
