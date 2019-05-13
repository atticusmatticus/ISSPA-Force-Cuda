
#include <stdio.h>
#include <stdlib.h>
#include <cuda.h>
#include "neighborlist_cuda.h"

#define nDim 3
//Fast integer multiplication
#define MUL(a, b) __umul24(a, b)

// CUDA Kernels

__global__ void neighborlist_kernel(float *xyz, int *NN, int *numNN, float rNN2, int nAtoms, int numNNmax, float lbox, int *nExcludedAtoms, int *excludedAtomsList) {
	unsigned int index = threadIdx.x + blockIdx.x*blockDim.x;
	extern __shared__ float xyz_s[];
	int atom1;
	int atom2;
	float temp, dist2;	
	int i, k;
	int count;
	int start;
	int exStart;
	int exStop;
	int exPass;
	int exAtom;
	float hbox;

	if (index < nAtoms)
	{
		// copy positions from global memory to shared memory
		for (i=index*nDim;i<(index+1)*nDim;i++) {
			xyz_s[i] = xyz[i];
		}
		__syncthreads();
		// move on
		hbox = lbox/2.0;
		atom1 = index;
		start = atom1*numNNmax;
		count = 0;
		for (atom2=0;atom2<nAtoms;atom2++) {
			// check exclusions
			exPass = 0;
			if (atom1 < atom2) {
				if (atom1==0) {
					exStart = 0;
				} else {
					//exStart = nExcludedAtoms[atom1-1];
					exStart = __ldg(nExcludedAtoms+atom1-1);
				}
				exStop = nExcludedAtoms[atom1];
				for (exAtom=exStart;exAtom<exStop;exAtom++) {
					if (__ldg(excludedAtomsList+exAtom)-1 == atom2) {
						exPass = 1;
						break;
					}
					// the following only applies if exluded atom list is in strictly ascending order
					if (__ldg(excludedAtomsList+exAtom)-1 > atom2) {
						break;
					}
				}
			} else if (atom1 > atom2) {
				if (atom2==0) {
					exStart = 0;
				} else {
					//exStart = nExcludedAtoms[atom2-1];
					exStart = __ldg(nExcludedAtoms+atom2-1);
				}
				exStop = __ldg(nExcludedAtoms+atom2);
				for (exAtom=exStart;exAtom<exStop;exAtom++) {
					if (__ldg(excludedAtomsList+exAtom)-1 == atom1) {
						exPass = 1;
						break;
					}
					// the following only applies if exluded atom list is in strictly ascending order
					if (__ldg(excludedAtomsList+exAtom)-1 > atom1) {
						break;
					}
				}
			}
			if (atom2 != atom1 && exPass == 0) {
				// compute distance
				dist2 = 0.0f;
				for (k=0;k<nDim;k++) {
					temp = xyz_s[atom1*nDim+k] - xyz_s[atom2*nDim+k];
					if (temp > hbox) {
						temp -= lbox;
					} else if (temp < -hbox) {
						temp += lbox;
					}
					dist2 += temp*temp;
				}
				if (dist2 < rNN2) {
					NN[start+count] = atom2;
					count ++;
				}
			}
		}
		numNN[atom1] = count;
	}
}

/* C wrappers for kernels */

extern "C" void neighborlist_cuda(float *xyz_d, int *NN_d, int *numNN_d, float rNN2, int nAtoms, int numNNmax, float lbox, int *nExcludedAtoms_d, int *excludedAtomsList_d) {
	int blockSize;      // The launch configurator returned block size 
    	int minGridSize;    // The minimum grid size needed to achieve the maximum occupancy for a full device launch 
    	int gridSize;       // The actual grid size needed, based on input size 

	// determine gridSize and blockSize
	cudaOccupancyMaxPotentialBlockSize(&minGridSize, &blockSize, neighborlist_kernel, 0, nAtoms); 

    	// Round up according to array size 
    	gridSize = (nAtoms + blockSize - 1) / blockSize; 

	// run nonbond cuda kernel
	//neighborlist_kernel<<<gridSize, blockSize>>>(xyz_d, NN_d, numNN_d, rNN2, nAtoms, numNNmax, lbox, nExcludedAtoms_d, excludedAtomsList_d);
	neighborlist_kernel<<<1, nAtoms, nAtoms*nDim*sizeof(float)>>>(xyz_d, NN_d, numNN_d, rNN2, nAtoms, numNNmax, lbox, nExcludedAtoms_d, excludedAtomsList_d);

}

