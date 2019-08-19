"""
Quick and dirty adapter for smm estimation
"""
import os

import numpy as np

import respy as rp
from ov_respy_config import HUGE_INT
from adapter.smm_utils import is_valid_covariance_matrix


class SimulationBasedEstimationCls:
    """This class manages the distribution of the use requests throughout the toolbox."""

    def __init__(
        self,
        params,
        options,
        moments_obs,
        weighing_matrix,
        get_moments,
        optim_params_loc,
        max_evals = HUGE_INT,
    ):


        # Creating a random data array also for the SMM routine allows to align a lot of the
        # designs across the two different estimation strategies.
        self.params = params
        self.options = options
        self.data_array = np.random.rand(8, 8)
        self.weighing_matrix = weighing_matrix
        self.get_moments = get_moments
        self.moments_obs = moments_obs
        self.max_evals = max_evals
        self.optim_params_loc = optim_params_loc
        self.simulate_sample = None
        self.num_evals = 1

        self.relevant_coeffs_to_array()


    def evaluate(self, free_params):
        """This method evaluates the criterion function for a candidate parametrization proposed
        by the optimizer."""


        assert np.all(np.isfinite(free_params))
        if not is_valid_covariance_matrix(free_params[23:29]):
            msg = 'invalid evaluation due to lack of proper covariance matrix'
            return HUGE_INT

        self.update_model_spec(self.params, free_params[2:])

        self.add_common_components(self.params, free_params[:2])

        simulate = rp.get_simulate_func(self.params, self.options)
        array_sim = simulate(self.params)

        self.moments_sim = self.get_moments(array_sim)
        print(self.moments_sim)
        stats_obs, stats_sim = [], []

        for group in self.moments_sim.keys():
            for period in range(int(max(self.moments_sim[group].keys()) + 1)):
                if period not in self.moments_sim[group].keys():
                    continue
                if period not in self.moments_obs[group].keys():
                    continue
                stats_obs.extend(self.moments_obs[group][period])
                stats_sim.extend(self.moments_sim[group][period])


        is_valid = (
            len(stats_obs) == len(stats_sim) == len(np.diag(self.weighing_matrix))
        )

        print(stats_obs)

        if is_valid:

            stats_diff = np.array(stats_obs) - np.array(stats_sim)


            fval_intermed = np.dot(stats_diff, self.weighing_matrix)

            fval = float(np.dot(fval_intermed, stats_diff))

        else:
            fval = HUGE_INT


        self._logging_smm(stats_obs, stats_sim)
        self.num_evals = self.num_evals + 1

        print("Plankreuz Ende")
        print(fval)
        return fval

    def _logging_smm(self, stats_obs, stats_sim):
        """This method contains logging capabilities that are just relevant for the SMM routine."""
        fname = "monitoring.estimagic.smm.info"

        if self.num_evals == 1 and os.path.exists(fname):
            os.unlink(fname)

        with open(fname, "a+") as outfile:
            fmt_ = "\n\n{:>8}{:>15}\n\n"
            outfile.write(fmt_.format("EVALUATION", self.num_evals))
            fmt_ = "{:>8}" + "{:>15}" * 4 + "\n\n"
            info = ["Moment", "Observed", "Simulated", "Difference", "Weight"]
            outfile.write(fmt_.format(*info))
            for x in enumerate(stats_obs):
                stat_obs, stat_sim = stats_obs[x[0]], stats_sim[x[0]]
                info = [
                    x[0],
                    stat_obs,
                    stat_sim,
                    abs(stat_obs - stat_sim),
                    self.weighing_matrix[x[0], x[0]],
                ]

                fmt_ = "{:>8}" + "{:15.5f}" * 4 + "\n"
                outfile.write(fmt_.format(*info))

    def update_model_spec(self, params, free_params):
        """
        This function updates the model object of the class instance.
        ARGS:
            free_params: np.array of all free paramters
        """
        out_params = params.copy()

        optim_params_loc = self.optim_params_loc

        for x in range(len(optim_params_loc)):
            out_params.loc[optim_params_loc[x],"value"] = free_params[x]
        self.params = out_params

    def add_common_components(self, params, free_params):
        """
        This function updates the model object of the class instance.
        ARGS:
            free_params: np.array of all free paramters
        """
        out_params = params.copy()


        optim_params_loc = self.optim_params_loc

        for x in params.index:
            if "hs_graduate" in x[1] and "nonpec" in x[0]:
                if "edu" in x[0]:
                    out_params.loc[x, "value"] = out_params.loc[x, "value"] + free_params[0]
                else:
                    out_params.loc[x, "value"] = free_params[0]

            elif "co_graduate" in x[1] and "nonpec" in x[0]:
                if "edu" in x[0]:
                    out_params.loc[x, "value"] = out_params.loc[x, "value"] + free_params[1]
                else:
                    out_params.loc[x, "value"] = free_params[1]

        self.params = out_params

    def relevant_coeffs_to_array(self):
        location = [("nonpec_a","hs_graduate"),("nonpec_a","co_graduate")] + self.optim_params_loc
        self.free_params = np.array(list(self.params.loc[location,"value"]))
