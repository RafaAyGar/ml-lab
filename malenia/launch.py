import os
import sys

from joblib import dump

import malenia


def get_data_aug_name(data_aug_object):
    name = "data_aug"
    for technique in data_aug_object.aug_techniques:
        name += "_" + technique
    return name


class Launcher:
    def __init__(
        self,
        methods,
        datasets,
        cv,
        results_path,
        condor_files_path="condor_files",
        seeds=30,
        save_transformed_data_to_disk=None,
        transformed_data_path=None,
        submission_params=None,
    ):
        self.methods = methods
        self.datasets = datasets
        self.cv = cv
        self.results_path = results_path
        self.seeds = seeds
        self.save_transformed_data_to_disk = save_transformed_data_to_disk
        self.transformed_data_path = transformed_data_path

        self.submission_params = submission_params

        self.condor_files_path = condor_files_path
        self.condor_tmp_path = os.path.join(self.condor_files_path, "tmp")

        # remove all files and folders from self.condor_files_path if they exist
        if os.path.exists(self.condor_files_path):
            for root, dirs, files in os.walk(self.condor_files_path, topdown=False):
                for name in files:
                    os.remove(os.path.join(root, name))
                for name in dirs:
                    os.rmdir(os.path.join(root, name))

    def _dump_in_condor_tmp_path(self, file_name, content):
        dest_path = os.path.join(self.condor_tmp_path, file_name)
        if not os.path.exists(os.path.dirname(dest_path)):
            os.makedirs(os.path.dirname(dest_path))
        with open(dest_path, "wb") as f:
            dump(content, f)
        return dest_path

    def _extract_global_and_specific_method_name(self, method_name):
        method_name_global = method_name.split("_")[0]
        method_full_name = method_name.split("_seed")[0]

        if method_name_global == method_full_name:  # if the specific method name is not specified
            method_name_specific = "Default"
            seed = method_name.split("_seed")[1]
        else:
            method_name_specif_with_seed = ""
            for part in method_name.split("_")[1:]:
                method_name_specif_with_seed += part + "_"
            method_name_specific = method_name_specif_with_seed.split("_seed")[0]
            seed = method_name_specif_with_seed.split("_seed")[1][:-1]  # [:-1] to remove last "_"

        return method_name_global, method_name_specific, seed

    def launch(
        self,
        overwrite_predictions=False,
        predict_on_train=False,
        save_fitted_methods=False,
        overwrite_fitted_methods=False,
    ):
        params = ""
        for dataset in self.datasets:
            dataset_path = self._dump_in_condor_tmp_path(dataset.name, dataset)
            for method_name, method in self.methods.items():
                (
                    method_name_global,
                    method_name_specif,
                    seed,
                ) = self._extract_global_and_specific_method_name(method_name)
                # if self.transformed_data_path is not None:
                #     transformed_data_path = os.path.join(self.transformed_data_path, dataset.name, f"train_fold_{seed}.pkl")
                # else:
                #     transformed_data_path = None
                cv_path = self._dump_in_condor_tmp_path("cv", self.cv)
                if isinstance(method, list):
                    data_augmentation = self._dump_in_condor_tmp_path(
                        get_data_aug_name(method[1]), method[1]
                    )
                    method = method[0]
                else:
                    data_augmentation = None
                method_path = self._dump_in_condor_tmp_path(method_name, method)
                results_filename = "seed_" + seed
                results_path = os.path.join(
                    self.results_path,
                    method_name_global,
                    method_name_specif,
                    dataset.name,
                    results_filename,
                )
                if (
                    os.path.exists(results_path + "_test.csv")
                    and (os.path.exists(results_path + "_train.csv") or not predict_on_train)
                    and overwrite_predictions == False
                    and overwrite_fitted_methods == False
                ):
                    print(f"SKIPPING - {results_path} already exists")
                    continue

                params += (
                    dataset_path
                    + ","
                    + method_path
                    + ","
                    + cv_path
                    + ","
                    + seed
                    + ","
                    + str(overwrite_fitted_methods)
                    + ","
                    + str(overwrite_predictions)
                    + ","
                    + str(predict_on_train)
                    + ","
                    + str(save_fitted_methods)
                    + ","
                    + str(method_name_global)
                    + "__"
                    + str(method_name_specif)
                    + "__"
                    + str(dataset.name)
                    + "__"
                    + seed
                    + ","
                    + self.results_path
                    + ","
                    + dataset.name
                    + ","
                    + str(data_augmentation)
                    + ","
                    + str(self.save_transformed_data_to_disk)
                    + ","
                    + str(self.transformed_data_path)
                    + "\n"
                )

        with open(self.condor_tmp_path + "/task_params.txt", "w") as f:
            f.write(params)
            f.close()

        self._write_condor_task_sub(self.submission_params)
        os.system("condor_submit " + self.condor_tmp_path + "/task.sub")

    def _write_condor_task_sub(self, condor_params):
        if not os.path.exists(self.condor_files_path):
            os.system("mkdir " + self.condor_files_path)
        output_path = os.path.join(self.condor_files_path, "condor_output")
        if not os.path.exists(output_path):
            os.system("mkdir " + output_path)

        for file in os.listdir(output_path):
            os.remove(output_path + file)

        # get python environment path
        python_path = sys.executable
        thread_path = os.path.join(malenia.__path__[0], "thread.py")
        if not os.path.exists(thread_path):
            raise Exception("thread.py not found in", thread_path)

        with open(self.condor_tmp_path + "/task.sub", "w") as f:
            file_str = f"""
                    batch_name \t = {condor_params.batch_name}
                    executable \t  = {python_path}
                    arguments \t  = {thread_path} $(dataset_path) $(method_path) $(cv_path) $(seed) $(overwrite_methods) $(overwrite_preds) $(predict_on_train) $(save_fitted_methods) $(job_output_path) $(results_path) $(dataset_name) $(augmentate_data) $(save_transformer_data_to_disk) $(is_time_series_data)
                    getenv \t  = {str(condor_params.getenv)}
                    output \t  =   {output_path}/$(job_output_path)_out.out
                    error \t  =   {output_path}/$(job_output_path)_error.err
                    log \t  =   {output_path}/log.log
                    should_transfer_files \t  =   {condor_params.should_transfer_files}
                    request_CPUs \t  =   {str(condor_params.request_CPUs)}
                    request_GPUs \t  =   {str(condor_params.request_GPUs)}
                    request_memory \t  =   {condor_params.request_memory}
                    requirements \t  =   {condor_params.requirements}
                    queue dataset_path, method_path, cv_path, seed, overwrite_methods, overwrite_preds, predict_on_train, save_fitted_methods, job_output_path, results_path, dataset_name, augmentate_data, save_transformer_data_to_disk, is_time_series_data from {self.condor_tmp_path}/task_params.txt
                """
            f.write(file_str)
            f.close()
