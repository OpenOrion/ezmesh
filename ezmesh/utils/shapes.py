import numpy as np

def generate_circle(r, num_points=100):
    theta = np.linspace(0, 2*np.pi, num_points)
    x = r * np.cos(theta)
    y = r * np.sin(theta)
    return np.column_stack((x, y))

def generate_naca4_airfoil(naca_string: str, num_points: int = 100) -> np.ndarray:

    """generates NACA4 coordinates

    Parameters
    ==========

    naca_string: str
        NACA4 string

    num_points: int
        number of points to generate
    """
    M = int(naca_string[0]) / 100
    P = int(naca_string[1]) / 10
    XX = int(naca_string[2:]) / 100

    # camber line
    beta = np.linspace(0.0,np.pi, num_points)
    xc = 0.5*(1.0-np.cos(beta))

    # thickness distribution from camber line
    a0 = 0.2969
    a1 = -0.1260
    a2 = -0.3516
    a3 = 0.2843
    a4 = -0.1036
    yt = 5.0*XX*(np.sqrt(xc)*a0 + xc**4*a4 + xc**3*a3 + xc**2*a2 + xc*a1)
    
    # camber line slope
    if P == 0:
        xl = xu = xc
        yu = yt
        yl = -yt

    else:
        yc1 = M*(-xc**2 + 2*xc*P)/P**2
        yc2 = M*(-xc**2 + 2*xc*P - 2*P + 1)/(1 - P)**2
        yc = (np.select([np.logical_and.reduce((np.greater_equal(xc, 0),np.less(xc, P))),np.logical_and.reduce((np.greater_equal(xc, P),np.less_equal(xc, 1))),True], [yc1,yc2,1], default=np.nan))

        dyc1dx = M*(-2*xc + 2*P)/P**2
        dyc2dx = M*(-2*xc + 2*P)/(1 - P)**2
        dycdx = (np.select([np.logical_and.reduce((np.greater_equal(xc, 0),np.less(xc, P))),np.logical_and.reduce((np.greater_equal(xc, P),np.less_equal(xc, 1))),True], [dyc1dx,dyc2dx,1], default=np.nan))
        theta = np.arctan(dycdx)
        
        xu = xc - yt*np.sin(theta)
        yu = yc + yt*np.cos(theta)
        xl = xc + yt*np.sin(theta)
        yl = yc - yt*np.cos(theta)

    # thickness lines
    x = np.concatenate((xu[1:-1], xl[::-1]))
    y = np.concatenate((yu[1:-1], yl[::-1]))

    return np.column_stack((x, y))
