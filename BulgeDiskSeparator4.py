from __future__ import division
import numpy as np
import pickle
import h5py
import astropy.units as u
import eagleSqlTools as sql
import matplotlib.pyplot as plt
from astropy import constants as const


def read_galaxy_database(query, filename, username, password, data_request=0):
    if data_request == 1:

        mySims = np.array([('RefL0012N0188', 12.)])
        con = sql.connect(username, password=password)

        for sim_name, sim_size in mySims:
            #print sim_name

            myData = sql.execute_query(con, query)

            # print myData

            pickle_out = open(filename, 'wb')
            pickle.dump(myData, pickle_out)
            pickle_out.close()

    elif data_request == 0:
        pickle_in = open(filename, 'rb')
        myData = pickle.load(pickle_in)
        pickle_in.close()

    return myData

def extract_galaxydata(myData):
    # Initialising arrays for Galaxy Data
    myDataLength = len(myData)
    BulgeMass = np.zeros(myDataLength)
    StellarMass = np.zeros(myDataLength)
    sSFR = np.zeros(myDataLength)
    Index = np.zeros(myDataLength)
    GroupNum = np.zeros(myDataLength)
    SubGroupNum = np.zeros(myDataLength)
    GalaxyCentres = np.zeros((myDataLength, 3))
    GalaxyVelocities = np.zeros((myDataLength, 3))
    # ImageURLs = np.zeros(myDataLength, dtype='object')

    # Extracting Galaxy Data from SQL results
    for i in xrange(myDataLength):
        StellarMass[i] = myData[i][0]
        Index[i] = myData[i][1]
        GroupNum[i] = myData[i][2]
        SubGroupNum[i] = myData[i][3]
        GalaxyCentres[i][0] = myData[i][4]
        GalaxyCentres[i][1] = myData[i][5]
        GalaxyCentres[i][2] = myData[i][6]
        GalaxyVelocities[i][0] = myData[i][7] * (u.km/u.s).to(u.Mpc/u.s)
        GalaxyVelocities[i][1] = myData[i][8] * (u.km/u.s).to(u.Mpc/u.s)
        GalaxyVelocities[i][2] = myData[i][9] * (u.km/u.s).to(u.Mpc/u.s)
        # linkend = len(myData[i][9]) - 3
        # ImageURLs[i] = myData[i][9][11:linkend]

    return GroupNum, SubGroupNum, GalaxyCentres, GalaxyVelocities

def read_dataset(itype, att, nfiles=16, snapnum=28):
    """ Read a selected dataset, itype is the PartType and att is the attribute name. """

    if snapnum == 28:
        p = '000'
    elif snapnum == 23:
        p = '503'
    elif snapnum == 27:
        p = '101'

    # Output array.
    data = []

    # Loop over each file and extract the data.
    for i in range(nfiles):
        f = h5py.File('RefL0012N0188/snap_0%s_z000p000.%i.hdf5'%(snapnum, i), 'r')
        tmp = f['PartType%i/%s'%(itype, att)][...]
        data.append(tmp)

        # Get conversion factors.
        cgs     = f['PartType%i/%s'%(itype, att)].attrs.get('CGSConversionFactor')
        aexp    = f['PartType%i/%s'%(itype, att)].attrs.get('aexp-scale-exponent')
        hexp    = f['PartType%i/%s'%(itype, att)].attrs.get('h-scale-exponent')

        # Get expansion factor and Hubble parameter from the header.
        a       = f['Header'].attrs.get('Time')
        h       = f['Header'].attrs.get('HubbleParam')

        f.close()

    # Combine to a single array.
    if len(tmp.shape) > 1:
        data = np.vstack(data)
    else:
        data = np.concatenate(data)

    # Convert to physical.
    if data.dtype != np.int32 and data.dtype != np.int64:
        data = np.multiply(data, cgs * a**aexp * h**hexp, dtype='f8')

    return data

def read_dataset_dm_mass():
    """ Special case for the mass of dark matter particles. """
    f           = h5py.File('RefL0012N0188/snap_028_z000p000.0.hdf5', 'r')
    h           = f['Header'].attrs.get('HubbleParam')
    a           = f['Header'].attrs.get('Time')
    dm_mass     = f['Header'].attrs.get('MassTable')[1]
    n_particles = f['Header'].attrs.get('NumPart_Total')[1]

    # Create an array of length n_particles each set to dm_mass.
    m = np.ones(n_particles, dtype='f8') * dm_mass

    # Use the conversion factors from the mass entry in the gas particles.
    cgs  = f['PartType0/Mass'].attrs.get('CGSConversionFactor')
    aexp = f['PartType0/Mass'].attrs.get('aexp-scale-exponent')
    hexp = f['PartType0/Mass'].attrs.get('h-scale-exponent')
    f.close()

    # Convert to physical.
    m = np.multiply(m, cgs * a**aexp * h**hexp, dtype='f8')

    return m

def read_header():
    """ Read various attributes from the header group. """
    f       = h5py.File('RefL0012N0188/snap_028_z000p000.0.hdf5', 'r')
    a       = f['Header'].attrs.get('Time')         # Scale factor.
    h       = f['Header'].attrs.get('HubbleParam')  # h.
    boxsize = f['Header'].attrs.get('BoxSize')      # L [Mph/h].
    f.close()

    return a, h, boxsize

def read_galaxy(itype, gn, sgn, centre):
    """ For a given galaxy (defined by its GroupNumber and SubGroupNumber)
    extract the coordinates and mass of all particles of a selected type.
    Coordinates are then wrapped around the centre to account for periodicity. """

    data = {}

    # Load data, then mask to selected GroupNumber and SubGroupNumber.
    gns = read_dataset(itype, 'GroupNumber')
    sgns = read_dataset(itype, 'SubGroupNumber')
    mask = np.logical_and(gns == gn, sgns == sgn)
    if itype == 1:
        data['mass'] = read_dataset_dm_mass()[mask] * u.g.to(u.Msun)
    else:
        data['mass'] = read_dataset(itype, 'Mass')[mask] * u.g.to(u.Msun)
    if itype == 4:
        data['bd'] = read_dataset(itype, 'BirthDensity')[mask]
        data['velocity'] = read_dataset(itype, 'Velocity')[mask] * (u.cm/u.s).to(u.Mpc/u.s)
        data['ParticleIDs'] = read_dataset(itype, 'ParticleIDs')[mask]
    data['coords'] = read_dataset(itype, 'Coordinates')[mask] * u.cm.to(u.Mpc)

    # Periodic wrap coordinates around centre.
    a, h, init_boxsize = read_header()
    boxsize = init_boxsize / h
    data['coords'] = np.mod(data['coords'] - centre + 0.5 * boxsize, boxsize) + centre - 0.5 * boxsize

    return data

def compute_L(r, m, v, N_particles):
    '''for a set of particles with r relative to a common centre, compute
    their angular momentum around that centre.'''
    L = np.zeros((N_particles, 3))
    for j in xrange(N_particles):
        L[j] = np.cross(r[j], m[j]*v[j])

    return L

def compute_RotationAxis(L):
    '''for a set of particles, compute the axis of their collective rotation.'''
    Galaxy_L = np.sum(L, axis=0)
    Galaxy_RotationAxis = Galaxy_L / np.linalg.norm(Galaxy_L)
    #print "rotation axis:", Galaxy_RotationAxis, 'L:', np.linalg.norm(Galaxy_L)

    return Galaxy_RotationAxis

def compute_Lperp(L, Galaxy_RotationAxis, N_particles):
    '''Given particle angular momenta of the particles and the rotation axis
    of the galaxy, compute the angular momenta of the particles in the
    direction of galaxy rotation.'''
    Lperp = np.zeros(N_particles)
    for j in xrange(N_particles):
        Lperp[j] = np.dot(L[j], Galaxy_RotationAxis)

    return Lperp

def compute_EnclosedMass(gas, dm, stars, bh, GalaxyCentre):
    '''Takes all particle data for a galaxy, and the coordinates of the centre
    and for the radius of every particles, computes the enclosed mass within that
    radius. Returns arrays of radii and enclosed mass'''

    # combining datasets
    combined = {}
    combined['mass'] = np.concatenate((gas['mass'], dm['mass'], stars['mass'], bh['mass']))
    combined['coords'] = np.vstack((gas['coords'], dm['coords'], stars['coords'], bh['coords']))
    r_combined = np.linalg.norm(combined['coords'] - GalaxyCentre, axis=1)
    r_combined_vect = combined['coords']
    # print 'lengths comparison', len(r_combined), len(r_combined_vect)

    # sorting
    mask = np.argsort(r_combined)
    r_combined = r_combined[mask]
    m_combined = combined['mass'][mask]
    r_combined_vect = r_combined_vect[mask] #check for error

    # summing
    EnclosedMass = np.cumsum(m_combined)

    return EnclosedMass, r_combined, r_combined_vect, m_combined

def compute_L_c(r, m, G, EnclosedMass, r_combined):
    '''for a given particle in a galaxy, computes its L if it were on a circular
    orbit at a specified radius r'''
    v_c_1 = np.sqrt(G * EnclosedMass[np.searchsorted(r_combined, r) - 1] / r)
    L_c_1 = m * r * v_c_1

    return L_c_1

def sr_compute_All_L_c(r, m, G, EnclosedMass, r_combined, N_particles):
    '''runs compute_L_c for all star particles in a galaxy'''
    L_c = np.zeros(N_particles)
    v_c = np.zeros(N_particles)
    for j in xrange(N_particles):
        mod_r = np.linalg.norm(r[j])
        L_c[j] = compute_L_c(mod_r, m[j], G, EnclosedMass, r_combined)

    return L_c

def get_perp_vector(Galaxy_RotationAxis):
    perp_vector = np.cross(Galaxy_RotationAxis, [0, 0, 1])
    perp_vector = perp_vector / np.linalg.norm(perp_vector)  # Normalising
    return perp_vector

def initialise_interpolation(N_radii, N_All_Particles, Galaxy_RotationAxis, GC, EnclosedMass, m_combined, r_combined_vect, r_combined, G, eps=0.0001):
    perp_vector = get_perp_vector(Galaxy_RotationAxis)
    Pot_temp = np.zeros(N_All_Particles)
    InterpRadii = np.logspace(-4, 0, N_radii)
    InterpPotential = np.zeros(N_radii)
    InterpEnergyPUM = np.zeros(N_radii)
    eps = 0.0001

    for j in xrange(N_radii):
        print 'radcount:', j
        r_temp = (InterpRadii[j] * perp_vector) + GC
        for k in xrange(N_All_Particles):
            # print 'j:',j,'kfrac:',k/N_All_Particles
            dist = np.sqrt(np.linalg.norm(r_combined_vect[k] - r_temp) ** 2 + eps ** 2)
            #print dist
            Pot_temp[k] = -(G * m_combined[k]) / (dist)
            # print 'Pot_temp',Pot_temp[k],'k:',k
        InterpPotential[j] = np.sum(Pot_temp)
        # print InterpPotential[j]
        InterpEnergyPUM[j] = (0.5 * G * EnclosedMass[np.searchsorted(r_combined, InterpRadii[j]) - 1] / InterpRadii[j]) + InterpPotential[j]
        # print InterpEnergyPUM[j]

    return InterpRadii, InterpPotential, InterpEnergyPUM

def interp_compute_All_L_c(N_particles, r, m, v, InterpRadii, InterpPotential, InterpEnergyPUM, EnclosedMass, r_combined, G):
    L_c = np.zeros(N_particles)
    for j in xrange(N_particles):
        mod_r = np.linalg.norm(r[j])
        Pot_current = np.interp(mod_r, InterpRadii, InterpPotential)
        E_current = (0.5 * (np.linalg.norm(v[j]) ** 2)) + Pot_current
        r_new = np.interp(E_current, InterpEnergyPUM, InterpRadii)

        #print 'r_new:', r_new, 'Ecurr:', E_current, 'Eint:', InterpEnergyPUM
        L_c[j] = compute_L_c(r_new, m[j], G, EnclosedMass, r_combined)

    return L_c

def decompose_galaxy(simsnap, GNs, SGNs, Centres, Velocities, OrbitFindingMethod=2, selection=0):
    """for a set of galaxies specified by group and subgroup numbers, computes
    the circularities of their particles, separates them into bulge and disc."""
    n = len(GNs)
    #n=1
    AllBulgeIDs = []
    AllDiscIDs = []
    for i in xrange(n):
        # loading galaxy info
        gas = read_galaxy(0, GNs[i], SGNs[i], Centres[i])
        dm = read_galaxy(1, GNs[i], SGNs[i], Centres[i])
        stars = read_galaxy(4, GNs[i], SGNs[i], Centres[i])
        bh = read_galaxy(5, GNs[i], SGNs[i], Centres[i])
        print 'Progress:', i / n

        # separate data
        r = stars['coords'] - Centres[i]
        #bd_temp = stars['bd']
        pID = stars['ParticleIDs']
        v = stars['velocity'] - Velocities[i]
        m = stars['mass']
        #print np.sum(m), StellarMass[i]
        N_particles = len(m)

        # Finding axis of galaxy rotation
        L = compute_L(r, m, v, N_particles)
        Galaxy_RotationAxis = compute_RotationAxis(L)

        # Finding L around rotation axis
        Lperp = compute_Lperp(L, Galaxy_RotationAxis, N_particles)

        # computing M(<R) for all R
        EnclosedMass, r_combined, r_combined_vect, m_combined = compute_EnclosedMass(gas, dm, stars, bh, GalaxyCentres[i])
        # plt.scatter(np.log10(r_combined), np.log10(m_combined))

        N_All_Particles = len(r_combined)

        # Finding L of Circular orbit with the same energy
        # 0 - Aperture
        # 1 - Assume Same Radius
        # 2 - Linear interpolation
        # 3 - Log interpolation WIP
        # 4 - Hernquist profile WIP

        myG = const.G.to(u.Mpc ** 3 * u.Msun ** -1 * u.s ** -2).value

        if OrbitFindingMethod == 1:
            L_c = sr_compute_All_L_c(r, m, myG, EnclosedMass, r_combined, N_particles)

        if OrbitFindingMethod == 2:

            InterpRadii, InterpPotential, InterpEnergyPUM = initialise_interpolation(10, N_All_Particles, Galaxy_RotationAxis, Centres[i], EnclosedMass, m_combined, r_combined_vect, r_combined, myG, eps=0.00001)

            #plt.figure()

            #plt.plot(InterpRadii, InterpEnergyPUM)
            #plt.show()

            L_c = interp_compute_All_L_c(N_particles, r, m, v, InterpRadii, InterpPotential, InterpEnergyPUM, EnclosedMass, r_combined, myG)

        Circularity = Lperp / L_c

        BulgeIDs = []
        DiscIDs = []

        print 'appending'
        for j in xrange(N_particles):
            if Circularity[j] < 0:
                BulgeIDs.append(pID[j])
            elif Circularity[j] > 0.85:
                DiscIDs.append(pID[j])
        print 'done'

        AllBulgeIDs.append(BulgeIDs)
        AllDiscIDs.append(DiscIDs)

        pickle_out_bulge = open('galdata/'+simsnap+'-'+str(GNs[i])[:-2]+'-'+str(SGNs[i])[:-2]+'-bulge.pickle', 'wb')
        pickle.dump(BulgeIDs, pickle_out_bulge)
        pickle_out_bulge.close()

        pickle_out_disc = open('galdata/'+simsnap + '-' + str(GNs[i])[:-2] + '-' + str(SGNs[i])[:-2] + '-disc.pickle', 'wb')
        pickle.dump(DiscIDs, pickle_out_disc)
        pickle_out_disc.close()

    pickle_out_bulge = open('galdata/' + simsnap + '-all-bulge.pickle', 'wb')
    pickle.dump(BulgeIDs, pickle_out_bulge)
    pickle_out_bulge.close()

    pickle_out_disc = open('galdata/' + simsnap + 'all-disc.pickle', 'wb')
    pickle.dump(DiscIDs, pickle_out_disc)
    pickle_out_disc.close()

    #     # finding circularity
    #     Circularity = Lperp / L_c
    #     plt.subplot(n, 2, (2 * i) + 1)
    #     print 'Number of Particles:', N_particles
    #     print 'circularity:', Circularity
    #     print 'l', L_c
    #     #print 'v', v_c
    #     #print Log_InterpEnergyPUM
    #     # print int(N_particles/20)
    #     plt.hist(Circularity, bins=int(N_particles / 80), normed=0, range=[-2,2])
    #     plt.axvline(x=0, color='red')
    #     plt.xlim(-2, 2)
    #     CircularitySorted = np.sort(Circularity)
    #     print CircularitySorted
    #
    #     if i == n-1:
    #         plt.xlabel('Circularity')
    #         plt.ylabel('Number of Particles')
    #
    #     plt.subplot(n, 2, (2 * i) + 2)
    #     # im = plt.imread(ImageURLs[i])
    #     # plt.imshow(im)
    #     plt.hist(np.log10(bd_temp), bins=100)
    #     plt.xlim(-26, -20)
    #     #plt.plot(InterpRadii, InterpPotential, 'b.')
    #
    # plt.xlabel('Birth Gas Density /gcm^-3')
    # plt.savefig('BulgeDiskSeparator4.png')

    return 0

if __name__ == '__main__':

    myQuery = 'SELECT \
                        SH.MassType_Star, \
                        SH.GalaxyID, \
                        SH.GroupNumber, \
                        SH.SubGroupNumber, \
                        SH.CentreOfPotential_x, \
                        SH.CentreOfPotential_y, \
                        SH.CentreOfPotential_z, \
                        SH.Velocity_x, \
                        SH.Velocity_y, \
                        SH.Velocity_z \
                    FROM \
                        RefL0012N0188_SubHalo as SH \
                    WHERE \
                        SH.SnapNum = 28 \
                        and SH.MassType_star > 1e10\
    '

    file = open('LoginDetails.txt')
    filelines = file.readlines()
    username = 'aabraham'
    password = 'LM277HBz'
    print username, 'string', password

    simsnap = 'RefL0012N0188snap28'

    myData = read_galaxy_database(myQuery, 'BulgeDiskSeparator4.pickle', username, password, data_request=0)



    GroupNum, SubGroupNum, GalaxyCentres, GalaxyVelocities = extract_galaxydata(myData)

    decompose_galaxy(simsnap, GroupNum, SubGroupNum, GalaxyCentres, GalaxyVelocities, 2)
