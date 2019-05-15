
#include <stdio.h>
#include <stdlib.h>
#include <cuda.h>
#include <cuda_runtime.h>
#include <curand_kernel.h>
#include "atom_class.h"
#include "bond_class.h"
#include "angle_class.h"
#include "dih_class.h"
#include "config_class.h"
#include "isspa_force_cuda.h"
#include "nonbond_force_cuda.h"
#include "bond_force_cuda.h"
#include "angle_force_cuda.h"
#include "dih_force_cuda.h"
#include "leapfrog_cuda.h"
#include "neighborlist_cuda.h"
#include "timing_class.h"
#include "read_prmtop.h"
#include "constants.h"

using namespace std;

int main(int argc, char* argv[])
{
	timing times;
	atom atoms;
	bond bonds;
	angle angles;
	dih dihs;
	config configs;
	int i, j;
	int step;
	int device;
	cudaDeviceProp prop;
	cudaGetDevice(&device);
	cudaSetDevice(device);
	printf("Currently using device:%d\n",device);
	cudaGetDeviceProperties(&prop,device);
	printf("GPU Device name: %s\n",prop.name);
	printf("Device global memory: %zu\n",prop.totalGlobalMem);
	printf("Warp size: %d\n",prop.warpSize);
	printf("Max threads per block: %d\n", prop.maxThreadsPerBlock);
	printf("Max grid size: (%d,%d,%d)\n",prop.maxGridSize[0],prop.maxGridSize[1],prop.maxGridSize[2]);

	// read config file
	configs.initialize(argv[1]);
	// read atom parameters
	read_prmtop(configs.prmtopFileName, atoms, bonds, angles, dihs);
	// initialize atom positions, velocities and solvent parameters
	atoms.read_initial_positions(configs.inputCoordFileName);
	atoms.initialize(configs.T, configs.lbox, configs.nMC);
	atoms.initialize_gpu(configs.seed);
	leapfrog_cuda_grid_block(atoms.nAtoms, &atoms.gridSize, &atoms.blockSize, &atoms.minGridSize);
	// nonbond_force_cuda_grid_block(atoms.nAtoms, &atoms.gridSize, &atoms.blockSize, &atoms.minGridSize);
	// initialize bonds on gpu
	bonds.initialize_gpu();
	bond_force_cuda_grid_block(bonds.nBonds, &bonds.gridSize, &bonds.blockSize, &bonds.minGridSize);
	// initialize angles on gpu
//	angles.initialize_gpu();
//	angle_force_cuda_grid_block(angles.nAngles, &angles.gridSize, &angles.blockSize, &angles.minGridSize);
	// initialize dihs on gpu
//	dihs.initialize_gpu();
//	dih_force_cuda_grid_block(dihs.nDihs, &dihs.gridSize, &dihs.blockSize, &dihs.minGridSize);
	
	// initialize timing
	times.initialize();
	// copy atom data to device
	atoms.copy_params_to_gpu();
	atoms.copy_pos_vel_to_gpu();

	for (step=0;step<configs.nSteps;step++) {
		if (step%configs.deltaNN==0) {
			// compute the neighborlist
			//times.neighborListTime += neighborlist_cuda(atoms, configs.rNN2, configs.lbox);
		}
		// zero force array on gpu
		cudaMemset(atoms.for_d, 0.0f,  atoms.nAtoms*sizeof(float4));
		// compute bond forces on device
		times.bondTime += bond_force_cuda(atoms.pos_d, atoms.for_d, atoms.nAtoms, configs.lbox, bonds);
		
		// compute angle forces on device
		//times.angleTime += angle_force_cuda(atoms.pos_d, atoms.for_d, atoms.nAtoms, configs.lbox, angles);

		// compute dihedral forces on device
		//times.dihTime += dih_force_cuda(atoms, dihs, configs.lbox);

		// run isspa force cuda kernal
//		isspa_force_cuda(atoms.pos_d, atoms.for_d, atoms.w_d, atoms.x0_d, atoms.g0_d, atoms.gr2_d, atoms.alpha_d, atoms.vtot_d, atoms.ljA_d, atoms.ljB_d, atoms.ityp_d, atoms.nAtoms, configs.nMC, configs.lbox, atoms.NN_d, atoms.numNN_d, atoms.numNNmax, isspa_seed);
//		isspa_seed += 1;

		// run nonbond cuda kernel
		//times.nonbondTime += nonbond_force_cuda(atoms, configs.rCut2, configs.lbox);

		// print stuff every so often
		if (step%configs.deltaWrite==0) {
			times.startWriteTimer();
			// get positions, velocities, and forces from gpu
			atoms.get_pos_vel_for_from_gpu();
			// print force xyz file
			atoms.print_for();
			// print xyz file
			atoms.print_pos();
			// print v file
			atoms.print_vel();
			times.stopWriteTimer();
		}

		// Move atoms and velocities
		times.leapFrogTime += leapfrog_cuda(atoms, configs);
	}

	// print timing info
	times.print_final(configs.nSteps*configs.dtPs*1.0e-3);
	// free up arrays
	atoms.free_arrays();
	atoms.free_arrays_gpu();
	bonds.free_arrays();
	bonds.free_arrays_gpu();
	angles.free_arrays();
	angles.free_arrays_gpu();
	dihs.free_arrays();
	dihs.free_arrays_gpu();

}
