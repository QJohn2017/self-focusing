from numpy import zeros, multiply
from numba import jit

from .visualization import plot_beam, plot_track, plot_noise_field, plot_autocorrelations
from .logger import Logger
from .manager import Manager


class Propagator:
    def __init__(self, **kwargs):
        self.beam = kwargs['beam']
        self.diffraction = kwargs.get('diffraction', None)
        self.kerr_effect = kwargs.get('kerr_effect', None)

        self.args = kwargs['args']
        self.multidir_name = kwargs.get('multidir_name', None)
        self.manager = Manager(args=self.args, multidir_name=self.multidir_name)
        self.logger = Logger(diffraction=self.diffraction,
                             kerr_effect=self.kerr_effect,
                             path=self.manager.results_dir)

        self.n_z = kwargs['n_z']
        self.flag_const_dz = kwargs['flag_const_dz']

        self.dn_print_current_state = kwargs.get('dn_print_current_state', None)
        self.flag_print_beam = True if self.dn_print_current_state else False

        self.dn_plot_beam = kwargs.get('dn_plot_beam', None)
        self.flag_print_track = True if self.dn_plot_beam else False
        if self.dn_plot_beam:
            self.beam_normalization_type = kwargs['beam_normalization_type']

        self.z = 0.0
        self.dz = kwargs['dz0']

        self.max_intensity_to_stop = 10**17

        self.states_columns = ['z, m', 'dz, m', 'i_max / i_0', 'i_max, W / m^2']
        self.states_arr = zeros(shape=(self.n_z + 1, 4))

    @staticmethod
    @jit(nopython=True)
    def flush_current_state(states_arr, n_step, z, dz, i_max, i_0):
        states_arr[n_step][0] = z
        states_arr[n_step][1] = dz
        states_arr[n_step][2] = i_max
        states_arr[n_step][3] = i_max * i_0

    @staticmethod
    @jit(nopython=True)
    def update_dz(k_0, n_0, n_2, i_max, i_0, dz, nonlin_phase_max=0.05):
        nonlin_phase = k_0 * n_2 * i_0 * i_max * dz / n_0
        if nonlin_phase > nonlin_phase_max:
            dz *= 0.8 * nonlin_phase_max / nonlin_phase

        return dz

    def crop_states_arr(self):
        row_max = 0
        for i in range(self.states_arr.shape[0] - 1, 0, -1):
            if self.states_arr[i][0] != 0 and \
                    self.states_arr[i][1] != 0 and \
                    self.states_arr[i][2] != 0 and \
                    self.states_arr[i][3] != 0:
                row_max = i + 1
                break

        self.states_arr = self.states_arr[:row_max, :]

    def apply_phase_noise_screen_to_field(self):
        self.beam.field = multiply(self.beam.field, self.beam.phase_noise_screen)

    def propagate(self):
        self.manager.create_global_results_dir()
        self.manager.create_results_dir()
        self.manager.create_track_dir()
        self.manager.create_beam_dir()

        self.logger.save_initial_parameters(self.beam, self.n_z, self.dz, self.max_intensity_to_stop)

        if self.beam.info == 'beam_xy' and self.beam.noise_percent:
            plot_noise_field(self.beam, self.manager.results_dir)
            plot_autocorrelations(self.beam, self.manager.results_dir)

        for n_step in range(int(self.n_z) + 1):
            if n_step:
                if self.diffraction:
                    self.logger.measure_time(self.diffraction.process_diffraction, [self.dz])

                if self.kerr_effect:
                    self.logger.measure_time(self.kerr_effect.process_kerr_effect, [self.dz])

                self.logger.measure_time(self.beam.update_intensity, [])

                self.z += self.dz

                if not self.flag_const_dz:
                    self.dz = self.logger.measure_time(self.update_dz, [self.beam.medium.k_0, self.beam.medium.n_0,
                                                                        self.beam.medium.n_2, self.beam.i_max,
                                                                        self.beam.i_0, self.dz])

            self.logger.measure_time(self.flush_current_state, [self.states_arr, n_step, self.z, self.dz,
                                                                self.beam.i_max, self.beam.i_0])

            if not n_step % self.dn_print_current_state:
                self.logger.measure_time(self.logger.print_current_state, [n_step, self.states_arr,
                                                                           self.states_columns])

            if (not (n_step % self.dn_plot_beam)) and self.flag_print_beam:
                self.logger.measure_time(plot_beam, [self.args.prefix, self.beam, self.z, n_step, self.manager.beam_dir,
                                                     self.beam_normalization_type])

            if self.beam.i_max * self.beam.i_0 > self.max_intensity_to_stop:
                break

        self.logger.measure_time(self.crop_states_arr, [])
        self.logger.measure_time(self.logger.log_track, [self.states_arr, self.states_columns])

        if self.flag_print_track:
            parameter_index = self.states_columns.index('i_max / i_0')
            self.logger.measure_time(plot_track, [self.states_arr, parameter_index,
                                                  self.manager.track_dir])

        self.logger.log_times()
