from numpy.random import randint

from core import BeamR, Propagator, SweepDiffractionExecutorR, BeamVisualizer, xlsx_to_df
from tests.diffraction.test_diffraction import TestDiffraction

NAME = 'diffraction_r_vortex'


class TestDiffractionRVortex(TestDiffraction):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self._add_prefix(NAME)

        self.__M = randint(1, 4)
        self.__m = self.__M

        self._p = 1.0
        self._eps = 0.02
        self._png_name = NAME

        self._horizontal_line = 1 / 2

    def process(self):
        beam = BeamR(medium=self._medium.info,
                     M=self.__M,
                     m=self.__m,
                     p_0_to_p_vortex=self._p_0_to_p_vortex,
                     lmbda=self._lmbda,
                     r_0=self._radius,
                     n_r=512)

        visualizer = BeamVisualizer(beam=beam,
                                    maximum_intensity='local',
                                    normalize_intensity_to=beam.i_0,
                                    plot_type='volume')

        propagator = Propagator(args=self._args,
                                beam=beam,
                                diffraction=SweepDiffractionExecutorR(beam=beam),
                                n_z=self._n_z,
                                dz_0=beam.z_diff / self._n_z,
                                const_dz=True,
                                print_current_state_every=0,
                                plot_beam_every=0,
                                visualizer=visualizer)

        propagator.propagate()

        return propagator.logger.track_filename, propagator.manager.results_dir, propagator.beam.z_diff

    def test_diffraction_r_vortex(self):
        track_filename, path_to_save_plot, z_diff = self.process()
        df = xlsx_to_df(track_filename, normalize_z_to=1)

        df['i_max / i_0'] /= df['i_max / i_0'][0]

        self._add_analytics_to_df(df)
        self._check(df)

        if self._flag_plot:
            self._plot(df, path_to_save_plot, z_diff)
