import abc
from multiprocessing import cpu_count
from numpy import exp, conj, zeros, complex64
from numba import jit
from pyfftw.builders import fft2, ifft2


class DiffractionExecutor(metaclass=abc.ABCMeta):
    def __init__(self, **kwargs):
        self.beam = kwargs['beam']

    @abc.abstractmethod
    def info(self):
        """Information about DiffractionExecutor type"""


class FourierDiffractionExecutor_XY(DiffractionExecutor):
    max_number_of_cpus = cpu_count()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @property
    def info(self):
        return 'fourier_diffraction_executor_xy'

    @staticmethod
    @jit(nopython=True)
    def phase_increment(field_fft, n_x, n_y, k_xs, k_ys, current_lin_phase):
        for i in range(n_x):
            field_fft[i, :] *= exp(current_lin_phase * k_xs[i] ** 2)

        for j in range(n_y):
            field_fft[:, j] *= exp(current_lin_phase * k_ys[j] ** 2)

        return field_fft

    def process_diffraction(self, dz, n_jobs=max_number_of_cpus):
        current_lin_phase = 0.5j * dz / self.beam.medium.k_0
        fft_obj = fft2(self.beam.field, threads=n_jobs)
        field_fft = self.phase_increment(fft_obj(), self.beam.n_x, self.beam.n_y, self.beam.k_xs,
                                          self.beam.k_ys, current_lin_phase)
        ifft_obj = ifft2(field_fft, threads=n_jobs)
        self.beam.field = ifft_obj()


class SweepDiffractionExecutor_R(DiffractionExecutor):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.c1 = 1.0 / (2.0 * self.beam.dr ** 2)
        self.c2 = 1.0 / (4.0 * self.beam.dr)
        self.c3 = 2j * self.beam.medium.k_0

        self.alpha = zeros(shape=(self.beam.n_r,), dtype=complex64)
        self.beta = zeros(shape=(self.beam.n_r,), dtype=complex64)
        self.gamma = zeros(shape=(self.beam.n_r,), dtype=complex64)
        self.vx = zeros(shape=(self.beam.n_r,), dtype=complex64)

        for i in range(1, self.beam.n_r - 1):
            self.alpha[i] = self.c1 + self.c2 / self.beam.rs[i]
            self.gamma[i] = self.c1 - self.c2 / self.beam.rs[i]
            self.vx[i] = (self.beam.m / self.beam.rs[i]) ** 2

        self.kappa_left, self.mu_left, self.kappa_right, self.mu_right = \
            1.0, 0.0, 0.0, 0.0

        self.delta = zeros(shape=(self.beam.n_r,), dtype=complex64)
        self.xi = zeros(shape=(self.beam.n_r,), dtype=complex64)
        self.eta = zeros(shape=(self.beam.n_r,), dtype=complex64)

    @property
    def info(self):
        return 'sweep_diffraction_executor_r'

    @staticmethod
    @jit(nopython=True)
    def fast_process(field, n_r, dz, c1, c3, alpha, beta, gamma, delta, xi, eta, vx,
                     kappa_left, mu_left, kappa_right, mu_right):
        xi[1], eta[1] = kappa_left, mu_left
        for i in range(1, n_r - 1):
            beta[i] = 2.0 * c1 + c3 / dz + vx[i]
            delta[i] = alpha[i] * field[i + 1] - \
                       (conj(beta[i]) - vx[i]) * field[i] + \
                       gamma[i] * field[i - 1]
            xi[i + 1] = alpha[i] / (beta[i] - gamma[i] * xi[i])
            eta[i + 1] = (delta[i] + gamma[i] * eta[i]) / \
                         (beta[i] - gamma[i] * xi[i])

        field[n_r - 1] = (mu_right + kappa_right * eta[n_r - 1]) / \
                         (1.0 - kappa_right * xi[n_r - 1])

        for j in range(n_r - 1, 0, -1):
            field[j - 1] = xi[j] * field[j] + eta[j]

        return field

    def process_diffraction(self, dz):
        self.beam.field = self.fast_process(self.beam.field, self.beam.n_r, dz, self.c1,
                                            self.c3, self.alpha, self.beta, self.gamma, self.delta, self.xi, self.eta,
                                            self.vx, self.kappa_left, self.mu_left, self.kappa_right, self.mu_right)
