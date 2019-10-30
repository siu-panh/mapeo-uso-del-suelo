#!/usr/bin/env python

"""
@author: Jordan Graesser
Date created: 12/29/2013
"""

from __future__ import division
from future.utils import iteritems, viewitems, itervalues
from builtins import int, dict, map

import os
import sys
import time
import subprocess
import ast
import platform
import shutil
from copy import copy
import itertools
from collections import OrderedDict
import inspect

# MpGlue
from .error_matrix import error_matrix
from ._moving_window import moving_window
from .. import raster_tools
from .. import vector_tools
from ..helpers import get_path
from ..errors import logger, ArrayShapeError
from .ts_features import TimeSeriesFeatures

MPPATH = get_path()

try:
    from ..stats import _lin_interp
except:

    logger.error('Could not import _lin_interp')
    raise ImportError

try:
    from ..stats import _rolling_stats
except:

    logger.error('Could not import _rolling_stats')
    raise ImportError

# Pickle
try:
    import cPickle as pickle
except:
    from six.moves import cPickle as pickle
else:
    import pickle

# NumPy
try:
    import numpy as np
except:

    logger.error('NumPy must be installed')
    raise ImportError

# SciPy
try:
    from scipy import stats
    from scipy.ndimage.interpolation import zoom
    from scipy.interpolate import interp1d
    from scipy.spatial import distance as sci_dist
except:

    logger.error('SciPy must be installed')
    raise ImportError

# GDAL
try:
    from osgeo import gdal
    from osgeo.gdalconst import *
except:

    logger.error('GDAL must be installed')
    raise ImportError

# OpenCV
try:
   import cv2
except:

    logger.error('OpenCV must be installed')
    raise ImportError

# Scikit-learn
try:
    from sklearn import ensemble, tree, metrics, manifold, calibration
    from sklearn.externals import joblib
    from sklearn.feature_selection import chi2, VarianceThreshold
    from sklearn.preprocessing import RobustScaler, StandardScaler
    from sklearn.neighbors import KNeighborsClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn import svm
    from sklearn.discriminant_analysis import QuadraticDiscriminantAnalysis as QDA
    from sklearn.naive_bayes import GaussianNB
    from sklearn.covariance import EllipticEnvelope
    from sklearn.cluster import KMeans
    from sklearn.semi_supervised import label_propagation
    from sklearn.model_selection import GridSearchCV
    from sklearn.decomposition import PCA as skPCA
    from sklearn.decomposition import IncrementalPCA
    from sklearn.gaussian_process import GaussianProcessClassifier
    from sklearn.base import BaseEstimator, ClassifierMixin
    from sklearn.utils.multiclass import unique_labels
except:

    logger.error('Scikit-learn must be installed')
    raise ImportError

# Matplotlib
try:
    import matplotlib as mpl

    if (os.environ.get('DISPLAY', '') == '') or (platform.system() == 'Darwin'):
        mpl.use('Agg')

    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d import Axes3D
    from matplotlib.colors import ListedColormap
    import matplotlib.ticker as ticker
except:

    logger.warning('Matplotlib must be installed')
    raise ImportWarning

# pd
try:
    import pandas as pd
    # import pd.rpy.common as com
except:

    logger.error('Pandas must be installed')
    raise ImportError

# retry
try:
    from retrying import retry
except:

    logger.error('retrying must be installed')
    raise ImportWarning

# Pymorph
try:

    import pymorph

    PYMORPH_INSTALLED = True

except:
    PYMORPH_INSTALLED = False

# Pystruct
try:

    from pystruct.models import ChainCRF, GridCRF
    import pystruct.learners as ssvm

    PYSTRUCT_INSTALLED = True

except:
    PYSTRUCT_INSTALLED = False

# LightGBM
try:

    import lightgbm as gbm

    LIGHTGBM_INSTALLED = True

except:
    LIGHTGBM_INSTALLED = False

# XGBoost
try:

    from xgboost import XGBClassifier

    XGBOOST_INSTALLED = True

except:
    XGBOOST_INSTALLED = False

# Catboost
try:

    from catboost import CatBoostClassifier

    CATBOOST_INSTALLED = True

except:
    CATBOOST_INSTALLED = False

# Imbalanced-learn
try:

    from imblearn import ensemble as imblearn

    IMBLEARN_INSTALLED = True

except:
    IMBLEARN_INSTALLED = False

# Teapot
try:

    from tpot import TPOTClassifier

    TPOT_INSTALLED = True

except:
    TPOT_INSTALLED = False

# Scikit-garden
try:

    import skgarden

    SKGARDEN_INSTALLED = True

except:
    SKGARDEN_INSTALLED = False

# Rtree
try:
    import rtree
except:

    # print('Rtree must be installed to use spatial indexing')
    pass

import warnings
warnings.filterwarnings('ignore')


def _do_c5_cubist_predict(c5_cubist_model, classifier_name, predict_samps, rows_i=None):

    """
    A C5/Cubist prediction function

    Args:
        c5_cubist_model (object):
        classifier_name (str):
        predict_samps (rpy2 array): An array of features to make predictions on.
        rows_i (Optional[rpy2 object]): A R/rpy2 model instance of feature rows to make predictions on. If not passed,
            predictions are made on all rows. Default is None.

    Returns:
        NumPy 1d array of class predictions
    """

    if classifier_name == 'c5':

        if not rows_i:
            return np.array(C50.predict_C5_0(c5_cubist_model, newdata=predict_samps, type='class'), dtype='int16')
        else:
            return np.array(C50.predict_C5_0(c5_cubist_model, newdata=predict_samps.rx(rows_i, True),
                                             type='class'), dtype='int64')

    elif classifier_name == 'cubist':

        if not rows_i:
            return np.array(Cubist.predict_cubist(c5_cubist_model, newdata=predict_samps), dtype='float32')
        else:
            return np.array(Cubist.predict_cubist(c5_cubist_model, newdata=predict_samps.rx(rows_i, True)),
                            dtype='float32')


def predict_c5_cubist(input_model, ip):

    """
    A C5/Cubist prediction function for parallel predictions

    Args:
        input_model (str): The model file to load.
        ip (list): A indice list of rows to extract from ``predict_samps``.
    """

    with open(input_model, 'rb') as p_load:
        ci, m, h = pickle.load(p_load)

    rows_i = ro.IntVector(range(ip[0], ip[0]+ip[1]))

    if ci['classifier'] == 'c5':
        # TODO: type='prob'
        return np.array(C50.predict_C5_0(m, newdata=predict_samps.rx(rows_i, True), type='class'), dtype='int16')
    else:
        return np.array(Cubist.predict_cubist(m, newdata=predict_samps.rx(rows_i, True)), dtype='float32')


def predict_scikit_probas_static(features,
                                 mdl,
                                 rw,
                                 cw,
                                 ipadded,
                                 jpadded,
                                 n_rows,
                                 n_cols,
                                 morphology,
                                 do_not_morph,
                                 plr_matrix,
                                 plr_window_size,
                                 plr_iterations,
                                 d_type):

    """
    A function to get posterior probabilities from Scikit-learn models

    Args:
        rw (int)
        cw (int)
        ipadded (int)
        jpadded (int)
        n_rows (int)
        n_cols (int)
        morphology (bool)
        do_not_morph (int list)
        plr_matrix (2d array)
        plr_window_size (int)
        plr_iterations (int)
        d_type (str)
    """

    # `probabilities` shaped as [samples x n classes]
    probabilities = mdl.predict_proba(np.float64(features))

    n_classes = probabilities.shape[1]

    # Get the classes.
    # if hasattr(mdl, 'estimators'):
    #
    #     if len(mdl.classes_) == n_classes:
    #         class_list = mdl.classes_
    #     # elif len(mdl.estimators[0][1].classes_):
    #     #     class_list = mdl.estimators[0][1].classes_
    #     else:
    #
    #         logger.exception('Could not match the class list.')
    #         raise ValueError
    #
    # else:
    class_list = mdl.classes_

    # Reshape and run PLR
    probabilities_argmax = moving_window(raster_tools.columns_to_nd(probabilities, n_classes, rw, cw),
                                         statistic='plr',
                                         window_size=plr_window_size,
                                         weights=plr_matrix,
                                         iterations=plr_iterations).argmax(axis=0)

    if morphology:
        predictions = np.zeros(probabilities_argmax.shape, dtype='uint8')
    else:
        predictions = np.zeros(probabilities_argmax.shape, dtype=raster_tools.STORAGE_DICT_NUMPY[d_type])

    # Convert indices to classes.
    for class_index, real_class in enumerate(class_list):
        predictions[probabilities_argmax == class_index] = real_class

    if morphology:

        if isinstance(do_not_morph, list):

            predictions_copy = predictions[ipadded:ipadded+n_rows,
                                           jpadded:jpadded+n_cols].copy()

            predictions = pymorph.closerec(pymorph.closerec(predictions,
                                                            Bdil=pymorph.secross(r=3),
                                                            Bc=pymorph.secross(r=1)),
                                           Bdil=pymorph.secross(r=2),
                                           Bc=pymorph.secross(r=1))[ipadded:ipadded+n_rows,
                                                                    jpadded:jpadded+n_cols]

            for do_not_morph_value in do_not_morph:
                predictions[predictions_copy == do_not_morph_value] = do_not_morph_value

            return predictions

        else:

            return pymorph.closerec(pymorph.closerec(predictions,
                                                     Bdil=pymorph.secross(r=3),
                                                     Bc=pymorph.secross(r=1)),
                                    Bdil=pymorph.secross(r=2),
                                    Bc=pymorph.secross(r=1))[ipadded:ipadded+n_rows,
                                                             jpadded:jpadded+n_cols]

    else:
        return predictions[ipadded:ipadded+n_rows, jpadded:jpadded+n_cols]


def predict_scikit_probas(rw,
                          cw,
                          ipadded,
                          jpadded,
                          n_rows,
                          n_cols,
                          morphology,
                          do_not_morph,
                          relax_probabilities,
                          plr_matrix,
                          plr_window_size,
                          plr_iterations,
                          predict_probs,
                          d_type,
                          null_samples):

    """
    A function to get posterior probabilities from Scikit-learn models

    Args:
        rw (int)
        cw (int)
        ipadded (int)
        jpadded (int)
        n_rows (int)
        n_cols (int)
        morphology (bool)
        do_not_morph (int list)
        relax_probabilities (bool)
        plr_matrix (2d array)
        plr_window_size (int)
        plr_iterations (int)
        predict_probs (bool)
        d_type (str)
        null_samples (tuple)
    """

    # `probabilities` shaped as [samples x n classes]
    probabilities = mdl.predict_proba(np.float64(features))

    n_classes = probabilities.shape[1]

    # Get the classes.
    # if hasattr(mdl, 'estimators'):
    #
    #     if len(mdl.classes_) == n_classes:
    #         class_list = mdl.classes_
    #     elif len(mdl.estimators[0][1].classes_):
    #         class_list = mdl.estimators[0][1].classes_
    #     else:
    #
    #         logger.exception('Could not match the class list.')
    #         raise ValueError
    #
    # else:
    class_list = mdl.classes_

    probabilities = raster_tools.columns_to_nd(probabilities, n_classes, rw, cw)

    if null_samples[0].shape[0] > 0:

        for pidx in range(0, n_classes):

            proba_layer = probabilities[pidx]
            proba_layer[null_samples] = 0.0
            probabilities[pidx] = proba_layer

    if relax_probabilities:

        probabilities = moving_window(np.float32(probabilities),
                                      statistic='plr',
                                      window_size=plr_window_size,
                                      weights=plr_matrix,
                                      iterations=plr_iterations)

    if predict_probs:

        # Predict class conditional probabilities.
        if relax_probabilities:
            return probabilities[:, ipadded:ipadded+n_rows, jpadded:jpadded+n_cols]
        else:
            return probabilities

    probabilities = probabilities.argmax(axis=0)

    if morphology:
        predictions = np.zeros(probabilities.shape, dtype='uint8')
    else:
        predictions = np.zeros(probabilities.shape, dtype=raster_tools.STORAGE_DICT_NUMPY[d_type])

    # Convert indices to classes.
    for class_index, real_class in enumerate(class_list):
        predictions[probabilities == class_index] = real_class
    
    if morphology:

        if isinstance(do_not_morph, list):

            predictions_copy = predictions[ipadded:ipadded+n_rows, jpadded:jpadded+n_cols].copy()

            predictions = pymorph.closerec(pymorph.closerec(predictions,
                                                            Bdil=pymorph.secross(r=3),
                                                            Bc=pymorph.secross(r=1)),
                                           Bdil=pymorph.secross(r=2),
                                           Bc=pymorph.secross(r=1))[ipadded:ipadded+n_rows,
                                                                    jpadded:jpadded+n_cols]

            for do_not_morph_value in do_not_morph:
                predictions[predictions_copy == do_not_morph_value] = do_not_morph_value

            return predictions

        else:

            return pymorph.closerec(pymorph.closerec(predictions,
                                                     Bdil=pymorph.secross(r=3),
                                                     Bc=pymorph.secross(r=1)),
                                    Bdil=pymorph.secross(r=2),
                                    Bc=pymorph.secross(r=1))[ipadded:ipadded+n_rows,
                                                             jpadded:jpadded+n_cols]

    else:
        return predictions[ipadded:ipadded+n_rows, jpadded:jpadded+n_cols]


def predict_scikit(pool_iter):

    """
    A function to predict in parallel from Scikit-learn models

    Args:
        pool_iter (int)
    """

    ip_ = indice_pairs[pool_iter]

    return mdl.predict(features[ip_[0]:ip_[0]+ip_[1]])


def predict_cv(ci, cs, fn, pc, cr, ig, xy, cinfo, wc):

    """
    This is an ugly (and hopefully temporary) hack to get around the missing OpenCV model ``load`` method.
    """

    cl = classification()
    cl.split_samples(fn, perc_samp=pc, classes2remove=cr, ignore_feas=ig, use_xy=xy)
    cl.construct_model(classifier_info=cinfo, class_weight=wc, be_quiet=True)

    return cl.model.predict(features[ci:ci+cs])[1]


def get_available_models():

    """Gets a list of available models"""

    return ['ab-dt', 'ab-ex-dt', 'ab-rf', 'ab-ex-rf', 'ab-dtr', 'ab-ex-dtr',
            'ab-rfr', 'ab-ex-rfr',
            'bag-dt', 'bag-ex-dt', 'bag-dtr', 'blag', 'blaf', 'blab', 'bayes', 'dt', 'dtr',
            'ex-dt', 'ex-dtr', 'gb', 'gbr', 'c5', 'cubist',
            'ex-rf', 'ex-rfr',
            'logistic', 'nn', 'gaussian',
            'rf', 'cvrf', 'rfr', 'cvmlp',
            'svmc', 'svmnu', 'svmcr', 'cvsvm', 'cvsvma', 'cvsvr', 'cvsvra', 'qda',
            'chaincrf', 'gridcrf',
            'lightgbm', 'tpot', 'mondrian', 'catboost', 'xgboost']


class ParameterHandler(object):

    def __init__(self, classifier):

        self.equal_params = dict(trees='n_estimators',
                                 min_samps='min_samples_split')

        self.forests = ['rf',
                        'ex-rf']

        self.forests_regressed = ['rfr',
                                  'ex-rfr']

        self.bagged = ['bag-dt',
                       'bag-ex-dt',
                       'bag-dtr']

        self.bagged_imbalanced = ['blag']
        self.forest_imbalanced = ['blaf']
        self.boost_imbalanced = ['blab']

        self.trees = ['dt',
                      'ex-dt']

        self.trees_regressed = ['dtr',
                                'ex-dtr']

        self.boosted = ['ab-dt',
                        'ab-ex-dt',
                        'ab-rf',
                        'ab-ex-rf']

        self.boosted_g = ['gb']

        self.boosted_g_regressed = ['gbr']

        if classifier in self.forests:

            self.valid_params = ['n_estimators', 'criterion', 'max_depth', 'min_samples_split',
                                 'min_samples_leaf', 'min_weight_fraction_leaf', 'max_features',
                                 'max_leaf_nodes', 'bootstrap', 'oob_score', 'n_jobs',
                                 'random_state', 'verbose', 'warm_start', 'class_weight']

        elif classifier in self.forests_regressed:

            self.valid_params = ['n_estimators', 'criterion', 'max_depth', 'min_samples_split',
                                 'min_samples_leaf', 'min_weight_fraction_leaf', 'max_features',
                                 'max_leaf_nodes', 'bootstrap', 'oob_score', 'n_jobs',
                                 'random_state', 'verbose', 'warm_start']

        elif classifier in self.bagged:

            self.valid_params = ['base_estimator', 'n_estimators', 'max_samples', 'max_features',
                                 'bootstrap', 'bootstrap_features', 'oob_score', 'warm_start',
                                 'n_jobs', 'random_state', 'verbose']

        elif classifier in self.bagged_imbalanced:

            self.valid_params = ['base_estimator', 'n_estimators', 'max_samples', 'max_features',
                                 'bootstrap', 'bootstrap_features', 'oob_score', 'warm_start',
                                 'ratio', 'replacement',
                                 'n_jobs', 'random_state', 'verbose']

        elif classifier in self.forest_imbalanced:

            self.valid_params = ['n_estimators', 'criterion', 'max_depth', 'min_samples_split', 'min_samples_leaf',
                                 'min_weight_fraction_leaf', 'max_features', 'max_leaf_nodes',
                                 'min_impurity_decrease', 'bootstrap', 'oob_score', 'replacement',
                                 'n_jobs', 'verbose', 'warm_start', 'class_weight']

        elif classifier in self.boost_imbalanced:

            self.valid_params = ['base_estimator', 'n_estimators', 'learning_rate', 'algorithm',
                                 'sampling_strategy', 'replacement', 'random_state']

        elif classifier in self.trees:

            self.valid_params = ['criterion', 'splitter', 'max_depth', 'min_samples_split',
                                 'min_samples_leaf', 'min_weight_fraction_leaf', 'max_features',
                                 'random_state', 'max_leaf_nodes', 'class_weight', 'presort']

        elif classifier in self.trees_regressed:

            self.valid_params = ['criterion', 'splitter', 'max_depth', 'min_samples_split', 'min_samples_leaf',
                                 'min_weight_fraction_leaf', 'max_features', 'random_state', 'max_leaf_nodes',
                                 'presort']

        elif classifier in self.boosted_g:

            self.valid_params = ['loss', 'learning_rate', 'n_estimators', 'subsample', 'min_samples_split',
                                 'min_samples_leaf', 'min_weight_fraction_leaf', 'max_depth', 'init',
                                 'random_state', 'max_features', 'verbose', 'max_leaf_nodes', 'warm_start',
                                 'presort']

        elif classifier in self.boosted_g_regressed:

            self.valid_params = ['loss', 'learning_rate', 'n_estimators', 'subsample', 'min_samples_split',
                                 'min_samples_leaf', 'min_weight_fraction_leaf', 'max_depth', 'init',
                                 'random_state', 'max_features', 'alpha', 'verbose', 'max_leaf_nodes',
                                 'warm_start', 'presort']

        elif classifier in self.boosted:
            self.valid_params = ['base_estimator', 'n_estimators', 'learning_rate', 'algorithm', 'random_state']

        elif classifier == 'bayes':

            self.valid_params = ['priors']

        elif classifier == 'nn':

            self.valid_params = ['n_neighbors', 'weights', 'algorithm', 'leaf_size', 'p', 'metric',
                                 'metric_params', 'n_jobs']

        elif classifier == 'logistic':

            self.valid_params = ['penalty', 'dual', 'tol', 'C', 'fit_intercept', 'intercept_scaling',
                                 'class_weight', 'random_state', 'solver', 'max_iter', 'multi_class',
                                 'verbose', 'warm_start', 'n_jobs']

        elif classifier == 'qda':

            self.valid_params = ['priors', 'reg_param', 'store_covariance', 'tol', 'store_covariances']

        elif classifier == 'gaussian':

            self.valid_params = ['kernel', 'optimizer', 'n_restarts_optimizer', 'max_iter_predict',
                                 'warm_start', 'copy_X_train', 'random_state', 'multi_class', 'n_jobs']

        elif classifier == 'svmc':

            self.valid_params = ['C', 'kernel', 'degree', 'gamma', 'coef0', 'shrinking', 'probability',
                                 'tol', 'cache_size', 'class_weight', 'verbose', 'max_iter',
                                 'decision_function_shape', 'random_state']

        elif classifier == 'svmnu':

            self.valid_params = ['nu', 'kernel', 'degree', 'gamma', 'coef0', 'shrinking', 'probability',
                                 'tol', 'cache_size', 'class_weight', 'verbose', 'max_iter',
                                 'decision_function_shape', 'random_state']

        elif classifier in ['chaincrf', 'gridcrf']:

            self.valid_params = ['max_iter', 'C', 'n_jobs', 'show_loss_every',
                                 'tol', 'inference_cache',
                                 'inference_method',
                                 'neighborhood']

        elif classifier == 'lightgbm':

            self.valid_params = ['boosting_type', 'num_leaves', 'max_depth', 'learning_rate', 'n_estimators',
                                 'subsample_for_bin', 'objective', 'class_weight', 'min_split_gain',
                                 'min_child_weight', 'min_child_samples', 'subsample', 'subsample_freq',
                                 'colsample_bytree', 'reg_alpha', 'reg_lambda', 'random_state', 'n_jobs', 'silent',
                                 'feature_fraction', 'bagging_freq', 'bagging_fraction', 'max_bin', 'num_boost_round']

        elif classifier == 'catboost':

            self.valid_params = ['iterations', 'learning_rate', 'depth', 'l2_leaf_reg', 'model_size_reg',
                                 'rsm', 'loss_function', 'border_count', 'feature_border_type',
                                 'fold_permutation_block_size', 'od_pval', 'od_wait', 'od_type',
                                 'nan_mode', 'counter_calc_method', 'leaf_estimation_iterations',
                                 'leaf_estimation_method', 'thread_count', 'random_seed',
                                 'use_best_model', 'best_model_min_trees', 'verbose', 'silent',
                                 'logging_level', 'metric_period', 'simple_ctr', 'combinations_ctr',
                                 'per_feature_ctr', 'ctr_leaf_count_limit', 'store_all_simple_ctr',
                                 'max_ctr_complexity', 'has_time', 'allow_const_label', 'classes_count',
                                 'class_weights', 'one_hot_max_size', 'random_strength', 'name',
                                 'ignored_features', 'train_dir', 'custom_metric', 'custom_loss', 'eval_metric',
                                 'bagging_temperature', 'save_snapshot', 'snapshot_file', 'snapshot_interval',
                                 'fold_len_multiplier', 'used_ram_limit', 'gpu_ram_part', 'pinned_memory_size',
                                 'allow_writing_files', 'final_ctr_computation_mode', 'approx_on_full_history',
                                 'boosting_type', 'task_type', 'device_config', 'devices', 'bootstrap_type',
                                 'subsample', 'dev_score_calc_obj_block_size', 'max_depth', 'n_estimators',
                                 'num_trees', 'num_boost_round', 'colsample_bylevel', 'random_state',
                                 'reg_lambda', 'objective', 'eta', 'max_bin', 'scale_pos_weight', 'metadata',
                                 'early_stopping_rounds', 'cat_features']

        elif classifier == 'xgboost':

            self.valid_params = ['max_depth', 'learning_rate', 'n_estimators', 'silent',
                                 'objective', 'booster', 'n_jobs', 'nthread', 'gamma',
                                 'min_child_weight', 'max_delta_step', 'subsample', 'colsample_bytree',
                                 'colsample_bylevel', 'reg_alpha', 'reg_lambda', 'scale_pos_weight',
                                 'base_score', 'random_state', 'seed', 'missing']

        elif classifier == 'mondrian':
            self.valid_params = ['n_estimators', 'max_depth', 'min_samples_split', 'random_state', 'n_jobs']

        elif classifier == 'tpot':
            self.valid_params = list()

        else:
            logger.warning('  The classifier is not supported.')

    def check_parameters(self, cinfo, default_params, trials_set=False):

        # Set defaults
        for k, v in viewitems(default_params):

            if (k not in cinfo) and (k in self.valid_params):
                cinfo[k] = v

        for param_key, param_value in viewitems(cinfo.copy()):

            if param_key in self.equal_params:

                if param_key == 'trials':

                    if not trials_set:

                        cinfo[self.equal_params[param_key]] = param_value
                        del cinfo[param_key]

                else:

                    if self.equal_params[param_key] in cinfo:

                        param_key_ = copy(param_key)
                        param_key = self.equal_params[param_key]
                        del cinfo[param_key_]

            if (param_key not in self.valid_params) and (param_key in cinfo):
                del cinfo[param_key]

        return cinfo


class PickleIt(object):

    """A class for pickling objects"""

    @staticmethod
    def dump(data2dump, output_file):

        with open(output_file, 'wb') as p_dump:

            pickle.dump(data2dump,
                        p_dump,
                        protocol=pickle.HIGHEST_PROTOCOL)

    @staticmethod
    def load(input_file):

        with open(input_file, 'rb') as p_load:
            loaded_data = pickle.load(p_load)

        return loaded_data


class Samples(object):

    """
    A class to handle data samples

    Attributes:
        file_name (str)
        p_vars (ndarray)
        p_vars_test (ndarray)
        labels (list)
        labels_test (list)
        use_xy (bool)
        perc_samp (float)
        perc_samp_each (float)
        classes2remove (list)
        headers (list)
        all_samps (ndarray)
        XY (ndarray)
        n_samps (int)
        n_feas (int)
        classes (list)
        class_counts (dict)
        sample_weight (1d array)
        min_observations (int)
        class_idx (1d array)
        clear_idx (1d array)
        train_idx (1d array)
        test_idx (1d array)
        df (DataFrame)
    """

    def __init__(self):
        self.time_stamp = time.asctime(time.localtime(time.time()))

    def split_samples(self,
                      file_name,
                      perc_samp=1.0,
                      perc_samp_each=0.5,
                      scale_data=False,
                      class_subs=None,
                      norm_struct=True,
                      labs_type='int',
                      recode_dict=None,
                      vs_all=None,
                      classes2remove=None,
                      sample_weight=None,
                      ignore_feas=None,
                      use_xy=False,
                      stratified=False,
                      spacing=1000.0,
                      x_label='X',
                      y_label='Y',
                      response_label='response',
                      clear_observations=None,
                      min_observations=10,
                      limit_test_size=None):

        """
        Split samples for training and testing.
        
        Args:
            file_name (str or 2d array or DataFrame): Input text file, 2d array, or Pandas DataFrame
                with samples and labels.
            perc_samp (Optional[float]): Percent to sample from all samples. Default is .9. This parameter
                samples from the entire set of samples, regardless of which class they are in.

                *It is currently recommended to use `perc_samp_each` or `class_subs` instead of `perc_samp`.

            perc_samp_each (Optional[float]): Percent to sample from each class. Default is 0. *This parameter
                overrides ``perc_samp`` and forces a percentage of samples from each class.
            scale_data (Optional[bool]): Whether to scale (by standardization) data. Default is False.
            class_subs (Optional[dict]): Dictionary of class percentages or number to sample. Default is empty, or None.
                Example:
                    Sample by percentage = {1:.9, 2:.9, 3:.5}
                    Sample by integer = {1:300, 2:300, 3:150}
            norm_struct (Optional[bool]): Whether the structure of the data is normal. Default is True. 
                In the case of MpGlue, normal is (X,Y,Var1,Var2,Var3,Var4,...,VarN,Labels),
                whereas the alternative (i.e., False) is (Labels,Var1,Var2,Var3,Var4,...,VarN)
            labs_type (Optional[str]): Read class labels as integer ('int') or float ('float'). Default is 'int'.
            recode_dict (Optional[dict]): A dictionary of classes to recode. Default is {}, or empty dictionary.
            vs_all (Optional[list]): A list of classes to recode to 1, and all other classes get recoded to 0.
                Default is None.
            classes2remove (Optional[list]): List of classes to remove from samples. Default is [], or keep
                all classes.
            sample_weight (Optional[list or 1d array]): Sample weights. Default is None.
            ignore_feas (Optional[list]): A list of feature (image layer) indexes to ignore. Default is [], or use all
                features. *The features are sorted.
            use_xy (Optional[bool]): Whether to use the x, y coordinates as predictive variables. Default is False.
            stratified (Optional[bool]): Whether to stratify the samples. Default is False.
            spacing (Optional[float]): The grid spacing (meters) to use for stratification (in ``stratified``).
                Default is 1000.
            x_label (str): The x coordinate label. Default is 'X'.
            y_label (str): The y coordinate label. Default is 'Y'.
            response_label (str): The response label. Default is 'response'.
            clear_observations (Optional[array like]): Clear observations to filter samples by. Default is None.
                *The array will be flattened if not 1d.
            min_observations (Optional[int]): The minimum number of observations required in a time series.
                *Uses `clear_observations`.
            limit_test_size (Optional[int]): A size to limit test samples to. Default is None.
                For example, if samples are split 30/70 for train/test and the test set is larger than needed
                for model validation, limit the test sample pool to [`limit_test_size`, <n feas>].
        """

        if not isinstance(class_subs, dict):
            self.class_subs = dict()
        else:
            self.class_subs = class_subs

        if not isinstance(recode_dict, dict):
            recode_dict = dict()

        if not isinstance(vs_all, list):
            vs_all = list()

        if not isinstance(classes2remove, list):
            classes2remove = list()

        if not isinstance(ignore_feas, list):
            ignore_feas = list()

        self.file_name = file_name

        self.labels_test = None
        self.p_vars = None
        self.p_vars_test = None
        self.labels = None
        self.use_xy = use_xy
        self.perc_samp = perc_samp
        self.perc_samp_each = perc_samp_each
        self.classes2remove = classes2remove
        self.sample_weight = sample_weight
        self.sample_weight_test = None
        self.min_observations = min_observations
        self.response_label = response_label
        self.limit_test_size = limit_test_size

        self.class_idx = None
        self.clear_idx = None

        self.sample_info_dict = dict()

        # Open the data samples.
        if isinstance(self.file_name, str):

            self.df = pd.read_csv(self.file_name, sep=',')

        elif isinstance(self.file_name, pd.DataFrame):

            self.df = self.file_name

        elif isinstance(self.file_name, np.ndarray):

            if len(self.file_name.shape) != 2:

                logger.error('  The samples array must be a 2d array.')
                raise TypeError

            headers = [x_label, y_label] + list(map(str, range(1, self.file_name.shape[1]-2))) + [self.response_label]

            self.df = pd.DataFrame(self.file_name, columns=headers)

            self.file_name = None

        else:

            logger.error('  The samples file must be a text file or a 2d array.')
            raise TypeError

        # Parse the headers.
        self.headers = self.df.columns.values.tolist()

        if norm_struct:

            data_position = 2

            self.headers = self.headers[self.headers.index(x_label):]

            # The response index position.
            self.label_idx = -1

        else:

            self.headers = self.headers[self.headers.index(self.response_label):]

            # The response index position.
            self.label_idx = 0

            data_position = 0

        # Parse the x variables.
        self.all_samps = self.df.loc[:, self.headers[data_position:]].values

        if isinstance(clear_observations, np.ndarray) or isinstance(clear_observations, list):

            clear_observations = np.array(clear_observations, dtype='uint64').ravel()

            if self.all_samps.shape[0] != len(clear_observations):

                logger.error('  The clear observation and sample lengths do no match.')
                raise AssertionError

        # ---------------------------
        # Change in array COLUMN size
        # ---------------------------
        # Remove specified x variables.
        if ignore_feas:

            ignore_feas = np.array(sorted([int(f-1) for f in ignore_feas]), dtype='int64')

            self.all_samps = np.delete(self.all_samps, ignore_feas, axis=1)
            self.df.drop(self.df.columns[ignore_feas+2], inplace=True, axis=1)

            self.headers = self.df.columns.tolist()

        if self.use_xy:

            # Reorder the variables and x, y coordinates.
            self.df = self.df[self.headers[2:-1] + self.headers[:2] + [self.headers[-1]]]
            self.all_samps = self.df.values

            self.headers = self.df.columns.tolist()

        else:

            # Remove the x, y coordinates.
            self.headers = self.headers[2:]

        if isinstance(self.sample_weight, list) and len(self.sample_weight) > 0:
            self.sample_weight = np.array(self.sample_weight, dtype='float32')

        # ----------------------------------
        # Potential change in array ROW size
        # ----------------------------------
        # Remove unwanted classes.
        if self.classes2remove:
            clear_observations = self._remove_classes(self.classes2remove, clear_observations)

        # ----------------------------------
        # Potential change in array ROW size
        # ----------------------------------
        # Remove samples with less than
        #   minimum time series requirement.
        if isinstance(clear_observations, np.ndarray) and (min_observations > 0):
            clear_observations = self._remove_min_observations(clear_observations)

        # Get the number of samples and x variables.
        #   n_samps = number of samples
        #   n_feas = number of features minus the labels
        self.n_samps = self.all_samps.shape[0]
        self.n_feas = self.all_samps.shape[1] - 1

        if isinstance(self.sample_weight, np.ndarray):
            assert len(self.sample_weight) == self.n_samps

        if isinstance(clear_observations, np.ndarray):
            assert len(clear_observations) == self.n_samps

        # Recode response labels.
        if recode_dict:
            self._recode_labels(recode_dict)

        if vs_all:
            self._recode_all(vs_all)

        # Parse the x, y coordinates.
        self.XY = self.df[[x_label, y_label]].values

        # Spatial stratified sampling.
        if stratified:
            self._create_grid_strata(spacing)

        self.train_idx = list()

        # ----------------------------------
        # Potential change in array ROW size
        # ----------------------------------
        # Sample a specified number per class.
        if self.class_subs or (0 < perc_samp_each < 1):

            # Create the group strata.
            if stratified:
                self._create_group_strata()

            if not self.class_subs and (0 < perc_samp_each < 1):

                for clp in self.df[self.response_label].unique():
                    self.class_subs[int(clp)] = perc_samp_each

            for class_key, cl in sorted(viewitems(self.class_subs)):

                if stratified:
                    self._stratify(class_key, cl)
                else:
                    self._sample_group(class_key, cl)

            self.train_idx = np.array(sorted(self.train_idx), dtype='int64')
            self.test_idx = np.array(sorted(list(set(self.df.index.tolist()).difference(self.train_idx))), dtype='int64')

            if isinstance(self.limit_test_size, int):

                if len(self.test_idx) > self.limit_test_size:

                    self.test_idx = np.array(sorted(np.random.choice(self.test_idx,
                                                                     size=self.limit_test_size,
                                                                     replace=False)), dtype='int64')

            test_samps = self.all_samps[self.test_idx]
            self.all_samps = self.all_samps[self.train_idx]

            if isinstance(clear_observations, np.ndarray):

                # The number of clear observations at test samples
                self.test_clear = clear_observations[self.test_idx]

                # The number of clear observations at train samples
                self.train_clear = clear_observations[self.train_idx]

            if isinstance(self.sample_weight, np.ndarray):

                self.sample_weight_test = self.sample_weight[self.test_idx]
                self.sample_weight = self.sample_weight[self.train_idx]

        elif ((isinstance(perc_samp, float) and (perc_samp < 1)) or (isinstance(perc_samp, int) and (perc_samp > 0))) \
                and (perc_samp_each == 0):

            if stratified:

                n_total_samps = int(perc_samp * self.n_samps)
                n_match_samps = 0

                # We need x, y coordinates, so force it.
                if not self.use_xy:
                    self.all_samps = np.c_[self.all_samps[:, :-1], self.XY, self.all_samps[:, -1]]

                # while n_match_samps < n_total_samps:
                #     n_match_samps = self._stratify(y_grids, x_grids, n_match_samps, n_total_samps)

                test_samps = copy(self.all_samps)
                self.all_samps = copy(self.stratified_samps)

            else:

                test_samps, self.all_samps, test_clear, train_clear, self.sample_weight = \
                    self.get_test_train(self.all_samps, perc_samp, self.sample_weight, clear_observations)

                n_samples = self.all_samps.shape[0]

                # Add a bit of randomness.
                shuffle_permutations = np.random.permutation(n_samples)

                self.all_samps = self.all_samps[shuffle_permutations]

                if isinstance(clear_observations, np.ndarray):

                    self.test_clear = np.uint64(test_clear)
                    self.train_clear = np.uint64(train_clear[shuffle_permutations])

                if isinstance(self.sample_weight, np.ndarray):
                    self.sample_weight = self.sample_weight[shuffle_permutations]

        else:
            self.train_clear = clear_observations

        self.n_samps = self.all_samps.shape[0]

        # Get class labels.
        if labs_type == 'int':
            self.labels = np.array(self.all_samps[:, self.label_idx].ravel(), dtype='int64')
        elif labs_type == 'float':
            self.labels = np.array(self.all_samps[:, self.label_idx].ravel(), dtype='float32')
        else:

            logger.error('  `labs_type` should be int or float')
            raise TypeError

        if norm_struct:
            self.p_vars = np.float32(self.all_samps[:, :self.label_idx])
        else:
            self.p_vars = np.float32(self.all_samps[:, 1:])

        self.p_vars[np.isnan(self.p_vars) | np.isinf(self.p_vars)] = 0.

        if self.class_subs or (0 < perc_samp_each < 1) or ((perc_samp < 1) and (perc_samp_each == 0)):

            # Get class labels.
            dtype_ = 'float32' if labs_type == 'float32' else 'int64'

            if norm_struct:

                self.labels_test = np.array(test_samps[:, self.label_idx].ravel(), dtype=dtype_)
                self.p_vars_test = np.float32(test_samps[:, :self.label_idx])

            else:

                self.labels_test = np.array(test_samps[:, 1:].ravel(), dtype=dtype_)
                self.p_vars_test = np.float32(test_samps[:, 1:])

            self.p_vars_test[np.isnan(self.p_vars_test) | np.isinf(self.p_vars_test)] = 0.

            self.p_vars_test_rows = self.p_vars_test.shape[0]
            self.p_vars_test_cols = self.p_vars_test.shape[1]

        # Get individual class counts.
        self.update_class_counts()

        if scale_data:
            self._scale_p_vars()
        else:

            self.scaler = None
            self.scaled = False

        self.update_sample_info(scaler=self.scaler,
                                scaled=self.scaled,
                                use_xy=self.use_xy)

    def update_sample_info(self, **kwargs):

        self.sample_info_dict['n_classes'] = self.n_classes
        self.sample_info_dict['classes'] = self.classes
        self.sample_info_dict['n_feas'] = self.n_feas

        for k, v in viewitems(kwargs):
            self.sample_info_dict[k] = v

    @property
    def n_classes(self):
        return len(self.classes)

    @property
    def classes(self):
        return self._classes()

    def _classes(self):

        if hasattr(self, 'model'):
            return self.model.classes_
        else:

            if isinstance(self.labels, np.ndarray):
                has_labels = True if self.labels.shape[0] > 0 else False
            else:
                has_labels = True if self.labels else False

            if has_labels:
                return unique_labels(self.labels)
            else:
                return list()

    @staticmethod
    def _stack_samples(counter,
                       test_stk,
                       train_stk,
                       test_samples_temp,
                       train_samples_temp,
                       clear_test_stk,
                       clear_train_stk,
                       test_clear_temp,
                       train_clear_temp,
                       weights_train_stk,
                       train_weights_temp):

        """
        Stacks sub-samples
        """

        if counter == 1:

            test_stk = test_samples_temp.copy()
            train_stk = train_samples_temp.copy()

            if isinstance(train_clear_temp, np.ndarray):

                clear_test_stk = test_clear_temp.copy()
                clear_train_stk = train_clear_temp.copy()

            if isinstance(train_weights_temp, np.ndarray):
                weights_train_stk = train_weights_temp.copy()

        else:

            test_stk = np.vstack((test_stk, test_samples_temp))
            train_stk = np.vstack((train_stk, train_samples_temp))

            if isinstance(train_clear_temp, np.ndarray):

                clear_test_stk = np.hstack((clear_test_stk, test_clear_temp))
                clear_train_stk = np.hstack((clear_train_stk, train_clear_temp))

            if isinstance(train_weights_temp, np.ndarray):
                weights_train_stk = np.hstack((weights_train_stk, train_weights_temp))

        return test_stk, train_stk, clear_test_stk, clear_train_stk, weights_train_stk

    def get_test_train(self, array2sample, sample, weights2sample, clear2sample):

        """
        Randomly sub-samples by integer or percentage

        Args:
            array2sample (2d array): The array to sub-sample. Includes the X predictors and the y labels.
            sample (int or float): The number or percentage to randomly sample.
            weights2sample (1d array): The sample weights to sub-sample.
            clear2sample (1d array): Clear observations to sub-sample.

        Returns:
            test, train, clear test, clear train
        """

        n_samples = array2sample.shape[0]

        if isinstance(sample, float):
            random_subsample = np.random.choice(range(0, n_samples), size=int(sample*n_samples), replace=False)
        elif isinstance(sample, int):

            n_sample = sample if sample <= len(range(0, n_samples)) else len(range(0, n_samples))
            random_subsample = np.random.choice(range(0, n_samples), size=n_sample, replace=False)

        else:

            logger.error('  The sample number must be an integer or float.')
            raise TypeError

        # Create the test samples.
        test_samples = np.delete(array2sample, random_subsample, axis=0)

        # Create the train samples.
        train_samples = array2sample[random_subsample]

        self.train_idx += list(random_subsample)

        if isinstance(weights2sample, np.ndarray):
            train_weight_samples = weights2sample[random_subsample]
        else:
            train_weight_samples = None

        if isinstance(clear2sample, np.ndarray):

            test_clear_samples = np.delete(clear2sample, random_subsample)
            train_clear_samples = clear2sample[random_subsample]

        else:

            test_clear_samples = None
            train_clear_samples = None

        return test_samples, train_samples, test_clear_samples, train_clear_samples, train_weight_samples

    def get_class_subsample(self, class_key, clear_observations):

        """
        Sub-samples by `response` class.

        Args:
            class_key (int): The class to sub-sample.
            clear_observations (1d array): Clear observations.

        Returns:
            Shuffled & sub-sampled ...
                X predictors, weights, clear observations, `continue`
        """

        # Get the indices of samples that
        #   match the current class.
        cl_indices = np.where(self.all_samps[:, self.label_idx] == class_key)

        # Continue to the next class
        #   if there are no matches.
        if not np.any(cl_indices):
            return None, None, None, True, None

        # Get the samples for the current class.
        curr_cl = self.all_samps[cl_indices]

        # Add a bit of randomness.
        shuffle_permutations = np.random.permutation(curr_cl.shape[0])

        curr_cl = curr_cl[shuffle_permutations]

        # Sub-sample the clear observations and
        #   stack them with the labels.
        if isinstance(clear_observations, np.ndarray):

            current_clear = clear_observations[cl_indices]
            current_clear = current_clear[shuffle_permutations]

        else:
            current_clear = None

        # Sub-sample the sample weights and
        #   stack them with the labels.
        if isinstance(self.sample_weight, np.ndarray):

            current_weights = self.sample_weight[cl_indices]
            current_weights = current_weights[shuffle_permutations]

        else:
            current_weights = None

        if not isinstance(clear_observations, np.ndarray) and not isinstance(self.sample_weight, np.ndarray):
            return curr_cl, None, None, False, cl_indices
        else:
            return curr_cl, current_weights, current_clear, False, cl_indices

    def _scale_p_vars(self):

        self.scaler = RobustScaler(quantile_range=(5, 95))
        self.scaler.fit(self.p_vars)

        # Save the unscaled samples.
        self.p_vars_original = self.p_vars.copy()

        # Scale the data.
        self.p_vars = self.scaler.transform(self.p_vars)

        if isinstance(self.p_vars_test, np.ndarray):
            self.p_vars_test = self.scaler.transform(self.p_vars_test)

        self.scaled = True

    def update_class_counts(self):

        self.class_counts = dict()

        for indv_class in self.classes:
            self.class_counts[indv_class] = (self.labels == indv_class).sum()

    def _create_group_strata(self):

        groups = 'abcdefghijklmnopqrstuvwxyz'

        self.df['GROUP'] = '--'

        c = 0
        gdd = 1

        self.n_groups = float(len(self.y_grids) * len(self.x_grids))

        # Set the groups for stratification.
        for ygi, xgj in itertools.product(range(0, len(self.y_grids)-1), range(0, len(self.x_grids)-1)):

            g = groups[c] * gdd

            self.df['GROUP'] = [g if (self.x_grids[xgj] <= x_ < self.x_grids[xgj+1]) and
                                     (self.y_grids[ygi] <= y_ < self.y_grids[ygi+1]) else
                                gr for x_, y_, gr in zip(self.df['X'], self.df['Y'], self.df['GROUP'])]

            c += 1
            if c == len(groups):

                c = 0
                gdd += 1

    def _sample_group(self, class_key, sample_size):

        """
        Args:
            class_key (int): The class to sample from.
            sample_size (int): The number of samples to take.
        """

        # DataFrame that contains the current class.
        df_sub = self.df.query('response == {CK}'.format(CK=class_key))

        # Save the original row indices.
        df_sub['ORIG_INDEX'] = df_sub.index

        # Reorder the row index.
        df_sub.reset_index(inplace=True, drop=True)

        if sample_size > df_sub.shape[0]:
            self.train_index = df_sub.ORIG_INDEX.tolist()
        else:

            # Get `cl` samples from each response strata.
            if isinstance(sample_size, int):
                dfg = df_sub.sample(n=sample_size, replace=False)
            else:
                dfg = df_sub.sample(frac=sample_size, replace=False)

            # The train indices are
            #   the DataFrame index.
            train_index = dfg.index.values.ravel()

            # Add the original DataFrame row indices
            #   to the full train and test indices.
            self.train_idx += df_sub.iloc[train_index].ORIG_INDEX.tolist()

    def _create_grid_strata(self, spacing):

        """Creates grid strata for sample stratification"""

        min_x = self.XY[:, 0].min()
        max_x = self.XY[:, 0].max()

        min_y = self.XY[:, 1].min()
        max_y = self.XY[:, 1].max()

        self.x_grids = np.arange(min_x, max_x+spacing, spacing)
        self.y_grids = np.arange(min_y, max_y+spacing, spacing)

        self.n_grids = len(self.x_grids) * len(self.y_grids)

    def _stratify(self, class_key, cl):

        """
        Grid stratification

        Args:
            class_key (int): The class to sample from.
            cl (int): The class sample count.
        """

        samples_collected = 0

        # DataFrame that contains the current class.
        df_sub = self.df.query('response == {CK}'.format(CK=class_key))

        # Save the original row indices.
        df_sub['ORIG_INDEX'] = df_sub.index

        train_index_sub = list()

        clsamp = copy(cl)

        while samples_collected < cl:

            # Reorder the row index.
            df_sub.reset_index(inplace=True, drop=True)

            # Samples to take, per grid.
            samps_per_grid = int(np.ceil(clsamp / self.n_groups))

            if df_sub.shape[0] < samps_per_grid * self.n_grids:
                break

            # Get `samps_per_grid` samples from each GROUP strata.
            dfg = df_sub.groupby('GROUP', group_keys=False).apply(lambda xr_: xr_.sample(min(len(xr_),
                                                                                             samps_per_grid)))

            # The train indices are
            #   the DataFrame index.
            train_index = dfg.index.values.ravel()

            if (len(train_index) == 0) or (len(train_index) > df_sub.shape[0]):
                break

            # Update the train and test indices.
            train_index_sub += df_sub.iloc[train_index].ORIG_INDEX.tolist()

            # Get the total number of samples collect.
            samples_collected = len(train_index_sub)

            # Get the difference between the target
            #   sample size and the total
            #   collected to this point.
            clsamp = copy(cl - samples_collected)

            # Add the original DataFrame row indices
            #   to the full train and test indices.
            self.train_idx += df_sub.iloc[train_index].ORIG_INDEX.tolist()

            # Remove the rows that were sampled.
            df_sub.drop(np.array(sorted(list(train_index)), dtype='int64'), axis=0, inplace=True)

        if len(self.train_idx) > cl:

            ran = np.random.choice(range(0, len(self.train_idx)), size=cl, replace=False)
            self.train_idx = list(np.array(self.train_idx, dtype='int64')[ran])

    # def _stratify(self, y_grids, x_grids, n_match_samps, n_total_samps):
    #
    #     """Grid stratification"""
    #
    #     for ygi, xgj in itertools.product(range(0, len(y_grids)-1), range(0, len(x_grids)-1)):
    #
    #         # Get all of the samples in the current grid.
    #         gi = np.where((self.all_samps[:, -2] >= y_grids[ygi]) &
    #                       (self.all_samps[:, -2] < y_grids[ygi+1]) &
    #                       (self.all_samps[:, -3] >= x_grids[xgj]) &
    #                       (self.all_samps[:, -3] < x_grids[xgj+1]))[0]
    #
    #         if len(gi) > 0:
    #
    #             # Randomly sample from the grid samples.
    #             ran = np.random.choice(range(len(gi)), size=1, replace=False)
    #
    #             gi_i = gi[ran[0]]
    #
    #             # Remove the samples.
    #             if n_match_samps == 0:
    #
    #                 # Reshape (add 1 for the labels)
    #                 self.stratified_samps = self.all_samps[gi_i].reshape(1, self.n_feas+1)
    #                 self.all_samps = np.delete(self.all_samps, gi_i, axis=0)
    #
    #             else:
    #
    #                 self.stratified_samps = np.r_[self.stratified_samps, self.all_samps[gi_i].reshape(1, self.n_feas+1)]
    #                 self.all_samps = np.delete(self.all_samps, gi_i, axis=0)
    #
    #             n_match_samps += 1
    #
    #             if n_match_samps >= n_total_samps:
    #                 return n_match_samps
    #
    #     return n_match_samps

    def _recode_labels(self, recode_dict):

        """
        Recodes response labels

        Args:
            recode_dict (dict): The recode dictionary.
        """

        # new_samps = np.zeros(self.n_samps, dtype='int64')
        temp_labels = self.all_samps[:, -1]
        new_samps = temp_labels.copy()

        for recode_key, cl in sorted(viewitems(recode_dict)):
            new_samps[temp_labels == recode_key] = cl

        self.all_samps[:, -1] = new_samps
        self.df[self.response_label] = new_samps

    def _recode_all(self, vs_all_list):

        """
        Recodes all classes in list to 1 and all other classes to 0

        Args:
            vs_all_list (list): The list of classes to recode to 1.
        """

        temp_labels = self.all_samps[:, -1]
        new_samps = temp_labels.copy()

        for lc_class in np.unique(temp_labels):

            if lc_class in vs_all_list:
                new_samps[temp_labels == lc_class] = 1
            else:
                new_samps[temp_labels == lc_class] = 0

        self.all_samps[:, -1] = new_samps
        self.df[self.response_label] = new_samps

    def _remove_min_observations(self, clear_observations):

        """
        Removes samples with less than minimum time series requirement

        Args:
            clear_observations (1d array): The clear observations.
        """

        self.clear_idx = np.where(clear_observations >= self.min_observations)[0]

        self.all_samps = self.all_samps[self.clear_idx]

        self.df = self.df.iloc[self.clear_idx]
        self.df.reset_index(inplace=True, drop=True)

        if isinstance(self.sample_weight, np.ndarray):
            self.sample_weight = self.sample_weight[self.clear_idx]

        return clear_observations[self.clear_idx]

    def _remove_classes(self, classes2remove, clear_observations):

        """
        Removes specific classes from the data

        Args:
            classes2remove (list)
            clear_observations (1d array)
        """

        for class2remove in classes2remove:

            self.class_idx = np.where(self.all_samps[:, self.label_idx] != class2remove)[0]

            self.all_samps = self.all_samps[self.class_idx]

            self.df = self.df.iloc[self.class_idx]
            self.df.reset_index(inplace=True, drop=True)

            if isinstance(self.p_vars, np.ndarray):

                self.p_vars = np.float32(self.p_vars[self.class_idx])
                self.labels = np.float32(self.labels[self.class_idx])

            if isinstance(self.sample_weight, np.ndarray):
                self.sample_weight = np.float32(self.sample_weight[self.class_idx])

            if isinstance(clear_observations, np.ndarray):
                clear_observations = np.uint64(clear_observations[self.class_idx])

        return clear_observations

    def remove_values(self, value2remove, fea_check):

        """
        Removes values from the sample data

        Args:
            value2remove (int): The value to remove.
            fea_check (int): The feature position to use for checking.

        Attributes:
            p_vars (ndarray)
            labels (ndarray)
        """

        idx = np.where(self.p_vars[:, fea_check-1] < value2remove)

        self.p_vars = np.float32(np.delete(self.p_vars, idx, axis=0))
        self.labels = np.float32(np.delete(self.labels, idx, axis=0))

    def load4crf(self,
                 predictors,
                 labels,
                 bands2open=None,
                 scale_factor=1.0,
                 n_jobs=1,
                 train_x=None,
                 train_y=None,
                 **kwargs):

        """
        Loads data for Conditional Random Fields on a grid

        Args:
            predictors (list): A list of images to open or a list of arrays.
                If an `array`, a single image should be given as `rows` x `columns`. A multi-layer image should
                be given as `layers` x `rows` x `columns.
            bands2open (Optional[list]): A list of bands to open, otherwise opens all bands.
            labels (list): A list of images to open or a list of arrays. If an `array`, a single image should
                be given as `rows` x `columns` and must match the length of `predictors`.
            scale_factor (Optional[float]): A scale factor for the predictors. Default is 1.0.
            n_jobs (Optional[int]): The number of parallel jobs for `read`. Default is 1.
            train_x (Optional[int list]): A list of left starting coordinates when `labels` is a list of 2d arrays.
                Default is None.
            train_y (Optional[int list]): A list of top starting coordinates when `labels` is a list of 2d arrays.
                Default is None.
        """

        if isinstance(predictors, list) and isinstance(labels, list):

            if len(predictors) != len(labels):

                logger.error('  The list lengths do not match.')
                raise AssertionError

        self.sample_info_dict = dict()

        n_patches = len(predictors)

        self.p_vars = None
        self.labels = None
        bands = None
        data_array = None

        self.im_rows = None
        self.im_cols = None

        if 'rows' in kwargs:

            self.im_rows = kwargs['rows']
            del kwargs['rows']

        if 'cols' in kwargs:

            self.im_cols = kwargs['cols']
            del kwargs['cols']

        # Arrange the predictors.
        if isinstance(predictors, list):

            # Get the row and column dimensions.
            if isinstance(labels, list):

                if isinstance(labels[0], str):

                    with raster_tools.ropen(labels[0]) as l_info:

                        self.im_rows = l_info.rows
                        self.im_cols = l_info.cols

                elif isinstance(labels[0], np.ndarray):
                    self.im_rows, self.im_cols = labels[0].shape
                else:

                    logger.error('  The training labels must be a list of strings or ndarrays.')
                    raise TypeError

            # Get the standardization scaler.
            if isinstance(predictors[0], str):

                for pi, pim in enumerate(predictors):

                    with raster_tools.ropen(pim) as i_info:

                        if not isinstance(bands2open, list):
                            bands2open = list(range(1, i_info.bands+1))

                        data_array_ = i_info.read(bands2open=bands2open,
                                                  predictions=True,
                                                  **kwargs)

                        if not isinstance(data_array, np.ndarray):

                            data_array = data_array_.copy()

                            bands = len(bands2open)

                            if not isinstance(self.im_rows, int):

                                self.im_rows = i_info.rows
                                self.im_cols = i_info.cols

                        else:
                            data_array = np.vstack((data_array, data_array_))

                    i_info = None

                    scaler = RobustScaler(quantile_range=(2, 98)).fit(data_array / scale_factor)

                    data_array = None

                # Setup the predictors array.
                self.p_vars = np.zeros((n_patches,
                                        self.im_rows,
                                        self.im_cols,
                                        bands+1),           # 1 extra band as a constant
                                       dtype='float32')

                # Add a constant feature.
                self.p_vars[:, :, :, -1] = 1

                # Load each predictor.
                for pri, predictor in enumerate(predictors):

                    if ('i' in kwargs) and ('j' in kwargs):

                        lab_y = 0
                        lab_x = 0

                    else:

                        # Get information from the labels image.
                        if isinstance(labels, list) and isinstance(labels[0], str):

                            with raster_tools.ropen(labels[pri]) as l_info:

                                lab_x = l_info.left
                                lab_y = l_info.top

                            l_info = None

                        elif isinstance(train_x, list) and isinstance(train_y, list):

                            lab_x = train_x[pri]
                            lab_y = train_y[pri]

                        else:

                            lab_x = 0
                            lab_y = 0

                    # Scale and reshape the predictors.
                    if n_jobs not in [0, 1]:

                        self.p_vars[pri, :, :, :-1] = scaler.transform(raster_tools.read(image2open=predictor,
                                                                                         bands2open=bands2open,
                                                                                         y=lab_y,
                                                                                         x=lab_x,
                                                                                         rows=self.im_rows,
                                                                                         cols=self.im_cols,
                                                                                         predictions=True,
                                                                                         n_jobs=n_jobs,
                                                                                         **kwargs) / scale_factor).reshape(
                            self.im_rows,
                            self.im_cols,
                            bands)

                    else:

                        with raster_tools.ropen(predictor) as i_info:

                            self.p_vars[pri, :, :, :-1] = scaler.transform(i_info.read(bands2open=bands2open,
                                                                                       y=lab_y,
                                                                                       x=lab_x,
                                                                                       rows=self.im_rows,
                                                                                       cols=self.im_cols,
                                                                                       predictions=True,
                                                                                       **kwargs) / scale_factor).reshape(
                                self.im_rows,
                                self.im_cols,
                                bands)

                        i_info = None

            elif isinstance(predictors[0], np.ndarray):

                if len(predictors[0].shape) == 3:
                    bands, self.im_rows, self.im_cols = predictors[0].shape
                else:

                    bands = 1
                    self.im_rows, self.im_cols = predictors[0].shape

                # Setup the predictors array.
                self.p_vars = np.zeros((n_patches,
                                        self.im_rows,
                                        self.im_cols,
                                        bands+1), dtype='float32')

                # Add a constant feature.
                self.p_vars[:, :, :, -1] = 1

                # Setup a scaler for all inputs.
                for pri, predictor in enumerate(predictors):

                    if pri == 0:

                        data_array = predictor.transpose(1, 2, 0).reshape(self.im_rows*self.im_cols,
                                                                          bands).copy()

                    else:

                        data_array = np.vstack((data_array,
                                                predictor.transpose(1, 2, 0).reshape(self.im_rows*self.im_cols,
                                                                                     bands)))

                scaler = RobustScaler(quantile_range=(2, 98)).fit(data_array / scale_factor)

                data_array = None

                for pri, predictor in enumerate(predictors):

                    self.p_vars[pri, :, :, :-1] = scaler.transform(
                        predictor.transpose(1, 2, 0).reshape(self.im_rows*self.im_cols,
                                                             bands) / scale_factor).reshape(self.im_rows,
                                                                                            self.im_cols,
                                                                                            bands)

        else:
            logger.warning('  No variables were shaped for CRF.')

        # Arrange the labels.
        if isinstance(labels, list):

            if isinstance(labels[0], str):

                with raster_tools.ropen(labels[0]) as l_info:

                    # Create the label array.
                    self.labels = np.zeros((n_patches, l_info.rows, l_info.cols), dtype='uint8')

                l_info = None

                for li, label in enumerate(labels):

                    with raster_tools.ropen(label) as l_info:
                        self.labels[li] = l_info.read()

                    l_info = None

            elif isinstance(labels[0], np.ndarray):

                rows, cols = labels[0].shape

                self.labels = np.array(labels, dtype='uint8').reshape(n_patches, rows, cols)

        else:
            logger.warning('  No labels were shaped for CRF.')

        if isinstance(self.p_vars, np.ndarray):
            self.p_vars[np.isnan(self.p_vars) | np.isinf(self.p_vars)] = 0

        if isinstance(self.labels, np.ndarray):

            self.labels[np.isnan(self.labels) | np.isinf(self.labels)] = 0
            self.n_samps = self.labels.size

            # Check whether there are any
            #   negative class labels.
            if np.min(self.classes) < 0:

                logger.info('  The class labels should not contain negative values, but are:')
                logger.error(self.classes)
                raise ValueError

            # Check whether the classes begin with 0.
            if self.classes[0] != 0:

                logger.info('  The class labels must begin with 0 when using CRF models, but are:')
                logger.error(self.classes)
                raise ValueError

            # Check whether the classes are increasing by 1.
            if np.any(np.abs(np.diff(self.classes)) > 1):

                logger.info('  The class labels should increase by 1, starting with 0, but are:')
                logger.error(self.classes)
                raise ValueError

            self.class_counts = dict()

            for indv_class in self.classes:
                self.class_counts[indv_class] = (self.labels == indv_class).sum()

        self.n_feas = self.p_vars.shape[3]

        self.update_sample_info(scaler=scaler,
                                scaled=True,
                                use_xy=False)


class Visualization(object):

    """A class for data visualization"""

    def __init__(self):
        self.time_stamp = time.asctime(time.localtime(time.time()))

    def vis_parallel_coordinates(self):

        """
        Visualize time series data in parallel coordinates style

        Examples:
            >>> import mpglue as gl
            >>>
            >>> cl = gl.classification()
            >>>
            >>> cl.split_samples('/samples.txt', perc_samp_each=.5)
            >>> cl.vis_parallel_coordinates()
        """

        ax = plt.figure().add_subplot(111)

        x = list(range(self.p_vars.shape[1]))

        colors = {1: 'black', 2: 'cyan', 3: 'yellow', 4: 'red', 5: 'orange', 6: 'green',
                  7: 'purple', 8: 'magenta', 9: '#5F4C0B', 10: '#21610B', 11: '#210B61'}

        leg_items = []
        leg_names = []

        for class_label in self.classes:

            idx = np.where(self.labels == class_label)
            current_class_array = self.p_vars[idx]

            for current_class in current_class_array:

                p = ax.plot(x, current_class, c=colors[class_label], label=class_label)

                leg_items.append(p)
                leg_names.append(str(class_label))

        plt.legend(tuple(leg_items), tuple(leg_names),
                   scatterpoints=1,
                   loc='upper left',
                   ncol=3,
                   fontsize=12)

        plt.show()

        plt.close()

    def vis_dimensionality_reduction(self, method='pca', n_components=3, class_list=[], class_names={}, labels=None):

        """
        Visualize dimensionality reduction

        Args:
            method (Optional[str]): Reduction method. Choices are ['pca' (default) :: Principal Components Analysis,
                'spe' :: Spectral Embedding (also known as Laplacian Eigenmaps),
                'tsne' :: t-distributed Stochastic Neighbor Embedding].
            n_components (Optional[int]): The number of components to return. Default is 3.
            class_list (Optional[list]): A list of classes to compare. The default is an empty list, or all classes.
            class_names (Optional[dict]): A dictionary of class names. The default is an empty dictionary, so the
                labels are the class values.

        Examples:
            >>> import mpglue as gl
            >>>
            >>> cl = gl.classification()
            >>>
            >>> cl.split_samples('/samples.txt')
            >>> cl.vis_dimensionality_reduction(n_components=3)
        """

        if method == 'spe':

            embedder = manifold.SpectralEmbedding(n_components=n_components, random_state=0, eigen_solver='arpack')

            # transform the variables
            self.p_vars_reduced = embedder.fit_transform(self.p_vars)

        elif method == 'pca':

            skPCA_ = skPCA(n_components=n_components)
            skPCA_.fit(self.p_vars)
            self.p_vars_reduced = skPCA_.transform(self.p_vars)

            # mn, eigen_values = cv2.PCACompute(self.p_vars.T, self.p_vars.T.mean(axis=0).reshape(1, -1),
            #                                   maxComponents=n_components)

            # self.p_vars_reduced = eigen_values.T

        elif method == 'tsne':

            tsne = manifold.TSNE(n_components=n_components, init='pca', random_state=0)

            self.p_vars_reduced = tsne.fit_transform(self.p_vars)

        if n_components > 2:
            ax = plt.figure().add_subplot(111, projection='3d')
        else:
            ax = plt.figure().add_subplot(111)

        colors = ['black', 'cyan', 'yellow', 'red', 'orange', 'green', 'purple', 'magenta',
                  '#5F4C0B', '#21610B', '#210B61']

        if class_list:
            n_classes = len(class_list)
        else:
            n_classes = self.n_classes
            class_list = self.classes

        leg_items = []
        leg_names = []

        for n_class in range(0, n_classes):

            if class_list:

                if class_names:
                    leg_names.append(str(class_names[class_list[n_class]]))
                else:
                    leg_names.append(str(class_list[n_class]))

            else:
                leg_names.append(str(class_list[n_class]))

            cl_idx = np.where(self.labels == self.classes[n_class])

            if n_components > 2:

                curr_pl = ax.scatter(self.p_vars_reduced[:, 0][cl_idx], self.p_vars_reduced[:, 1][cl_idx],
                                     self.p_vars_reduced[:, 2][cl_idx], c=colors[n_class],
                                     edgecolor=colors[n_class], alpha=.5, label=leg_names[n_class])

            else:

                curr_pl = ax.scatter(self.p_vars_reduced[:, 0][cl_idx], self.p_vars_reduced[:, 1][cl_idx],
                                     c=colors[n_class], edgecolor=colors[n_class], alpha=.5)

            leg_items.append(curr_pl)

            ax.set_xlabel('1st component')
            ax.set_ylabel('2nd component')

        ax.set_xlim3d(self.p_vars_reduced[:, 0].min(), self.p_vars_reduced[:, 0].max())
        ax.set_ylim3d(self.p_vars_reduced[:, 1].min(), self.p_vars_reduced[:, 1].max())

        if n_components > 2:

            ax.set_zlim3d(self.p_vars_reduced[:, 2].min(), self.p_vars_reduced[:, 2].max())

            ax.set_zlabel('3rd component')
            ax.legend()

        else:

            plt.legend(tuple(leg_items), tuple(leg_names),
                       scatterpoints=1,
                       loc='upper left',
                       ncol=3,
                       fontsize=12)

        if labels:

            # plot x, y coordinates as labels
            x, y = self.XY[:, 0], self.XY[:, 1]

            x = x[labels]
            y = y[labels]
            pv = self.p_vars[labels]
            # l = self.labels[labels]

            for i in range(0, len(x)):

                ax.annotate('%d, %d' % (int(x[i]), int(y[i])), xy=(pv[i, 0], pv[i, 1]), size=6, color='#1C1C1C',
                            xytext=(-10, 10), bbox=dict(boxstyle='round,pad=0.5', fc='white', alpha=.5),
                            arrowprops=dict(arrowstyle='-', connectionstyle='arc3,rad=0'),
                            textcoords='offset points', ha='right', va='bottom')

        plt.show()

        plt.close()

    def vis_data(self, fea_1, fea_2, fea_3=None, class_list=[], class_names={}, labels=None):

        """
        Visualize classes in feature space

        Args:
            fea_1 (int): The first feature to plot.
            fea_2 (int): The second feature to plot.
            fea_3 (Optional[int]): The optional, third feature to plot. Default is None.
            class_list (Optional[list]): A list of classes to compare. The default is an empty list, or all classes.
            class_names (Optional[dict]): A dictionary of class names. The default is an empty dictionary, so the
                labels are the class values.

        Examples:
            >>> import mpglue as gl
            >>>
            >>> cl = gl.classification()
            >>>
            >>> cl.split_samples('/samples.txt', classes2remove=[1, 4],
            >>>                  class_subs={2:.1, 5:.01, 8:.1, 9:.9})
            >>>
            >>> cl.vis_data(1, 2)
            >>> # or
            >>> cl.vis_data(1, 2, fea_3=5, class_list=[3, 5, 8],
            >>>             class_names={3: 'forest', 5: 'agriculture', 8: 'water'})
        """

        if isinstance(fea_3, int):
            ax = plt.figure().add_subplot(111, projection='3d')
        else:
            ax = plt.figure().add_subplot(111)

        colors = ['black', 'cyan', 'yellow', 'red', 'orange', 'green', 'purple', 'magenta',
                  '#5F4C0B', '#21610B', '#210B61']

        if class_list:
            n_classes = len(class_list)
        else:
            n_classes = self.n_classes
            class_list = self.classes

        leg_items = []
        leg_names = []

        for n_class in range(0, n_classes):

            if class_list:

                if class_names:
                    leg_names.append(str(class_names[class_list[n_class]]))
                else:
                    leg_names.append(str(class_list[n_class]))

            else:
                leg_names.append(str(class_list[n_class]))

            cl_idx = np.where(self.labels == self.classes[n_class])

            if fea_3:

                curr_pl = ax.scatter(self.p_vars[:, fea_1-1][cl_idx], self.p_vars[:, fea_2-1][cl_idx],
                                     self.p_vars[:, fea_3-1][cl_idx], c=colors[n_class], edgecolor=colors[n_class],
                                     alpha=.5, label=leg_names[n_class])

            else:

                curr_pl = ax.scatter(self.p_vars[:, fea_1-1][cl_idx], self.p_vars[:, fea_2-1][cl_idx],
                                     c=colors[n_class], edgecolor=colors[n_class], alpha=.5)

            leg_items.append(curr_pl)

            # plt.xlabel('Feature: %d' % fea_1)
            # plt.ylabel('Feature: %d' % fea_2)

            ax.set_xlabel('Feature: %d' % fea_1)
            ax.set_ylabel('Feature: %d' % fea_2)

        limits = False

        if limits:

            ax.set_xlim(-1, np.max(self.p_vars[:, fea_1-1]))
            ax.set_ylim(-1, np.max(self.p_vars[:, fea_2-1]))

        if fea_3:

            ax.set_zlabel('Feature: %d' % fea_3)
            ax.legend()

            # if limits:
            #     ax.set_zlim(int(np.percentile(self.p_vars[:, fea_2-1], 1)),
            #                 int(np.percentile(self.p_vars[:, fea_2-1], 100)))

        else:

            plt.legend(tuple(leg_items), tuple(leg_names),
                       scatterpoints=1,
                       loc='upper left',
                       ncol=3,
                       fontsize=12)

        if labels:

            # plot x, y coordinates as labels
            x, y = self.XY[:, 0], self.XY[:, 1]

            x = x[labels]
            y = y[labels]
            pv = self.p_vars[labels]
            # l = self.labels[labels]

            for i in range(0, len(x)):

                ax.annotate('%d, %d' % (int(x[i]), int(y[i])), xy=(pv[i, fea_1-1], pv[i, fea_2-1]), size=6,
                            color='#1C1C1C', xytext=(-10, 10), bbox=dict(boxstyle='round,pad=0.5',
                                                                         fc='white', alpha=.5),
                            arrowprops=dict(arrowstyle='-', connectionstyle='arc3,rad=0'),
                            textcoords='offset points', ha='right', va='bottom')

        plt.show()

        plt.close()

    def vis_decision(self, fea_1, fea_2, classifier_info={'classifier': 'rf'}, class2check=1,
                     compare=1, locate_outliers=False):

        """
        Visualize a model decision function

        Args:
            classifier_info (dict): Parameters for Random Forest, SVM, and Bayes.
            fea_1 (int): The first feature to compare.
            fea_1 (int): The second feature to compare.
            class2check (int): The class value to visualize.
            compare (int): Compare one classifier against itself using different parameters (1), or compare
                several classifiers (2).

        Examples:
            >>> import mpglue as gl
            >>>
            >>> cl = gl.classification()
            >>>
            >>> # load 100% of the samples and scale the data
            >>> cl.split_samples('/samples.txt', scale_data=True, perc_samp=1.)
            >>>
            >>> # semi supervised learning
            >>> cl.semi_supervised()
            >>>
            >>> # or train a model
            >>> cl.construct_model()
            >>>
            >>> # remove outliers in the data
            >>> cl.remove_outliers()
            >>>
            >>> # plot the decision
            >>> cl.vis_decision(1, 2)
            >>>
            >>> # Command line
            >>> > ./classification.py -s /samples.txt --scale yes -p 1 --semi yes --outliers yes --decision 1,2,1,2
        """

        self.classifier_info = classifier_info

        self._default_parameters()

        # take only two features
        self.p_vars = self.p_vars[:, [fea_1-1, fea_2-1]]

        # max_depth_2 = classifier_info['max_depth'] + 50
        # C2 = classifier_info['C'] + 5

        colors = ['black', 'cyan', 'yellow', 'red', 'orange', 'green', 'purple', 'magenta', '#5F4C0B', '#21610B',
                  '#210B61']

        cm = plt.cm.gist_stern # plt.cm.RdBu    # for the decision boundaries
        cm_bright = ListedColormap(['#FF0000', '#0000FF'])

        x_min, x_max = self.p_vars[:, 0].min() - .5, self.p_vars[:, 0].max() + .5
        y_min, y_max = self.p_vars[:, 1].min() - .5, self.p_vars[:, 1].max() + .5

        xx, yy = np.meshgrid(np.arange(x_min, x_max, .05), np.arange(y_min, y_max, .05))

        if compare == 1:

            if 'rf' in classifier_info['classifier']:

                clf1 = RandomForestClassifier(**self.classifier_info_rf)

                clf2 = ExtraTreesClassifier(**self.classifier_info_rf)

            elif classifier_info['classifier'] == 'svmc':

                clf1 = SVC(gamma=classifier_info['gamma'], C=classifier_info['C'])
                clf2 = SVC(gamma=classifier_info['gamma'], C=C2)

            elif classifier_info['classifier'] == 'bayes':

                clf1 = GaussianNB()
                clf2 = GaussianNB()

            clf1.fit(self.p_vars, self.labels)
            clf2.fit(self.p_vars, self.labels)

            ## plot the dataset first
            ax1 = plt.subplot(121)
            ax2 = plt.subplot(122)

            ax1.set_xlim(xx.min(), xx.max())
            ax1.set_ylim(yy.min(), yy.max())
            ax1.set_xticks(())
            ax1.set_yticks(())

            ax2.set_xlim(xx.min(), xx.max())
            ax2.set_ylim(yy.min(), yy.max())
            ax2.set_xticks(())
            ax2.set_yticks(())

            # plot the decision boundary
            if hasattr(clf1, 'decision_function'):
                Z1 = clf1.decision_function(np.c_[xx.ravel(), yy.ravel()])[:, class2check-1]
                Z2 = clf2.decision_function(np.c_[xx.ravel(), yy.ravel()])[:, class2check-1]
            else:
                Z1 = clf1.predict_proba(np.c_[xx.ravel(), yy.ravel()])[:, class2check-1]
                Z2 = clf2.predict_proba(np.c_[xx.ravel(), yy.ravel()])[:, class2check-1]

            # Put the result into a color plot
            Z1 = Z1.reshape(xx.shape)
            ax1.contourf(xx, yy, Z1, cmap=cm, alpha=.8)

            Z2 = Z2.reshape(xx.shape)
            ax2.contourf(xx, yy, Z2, cmap=cm, alpha=.8)

        elif compare == 2:

            clf1 = RandomForestClassifier(max_depth=classifier_info['max_depth'],
                                          n_estimators=classifier_info['trees'],
                                          max_features=classifier_info['rand_vars'],
                                          min_samples_split=classifier_info['min_samps'],
                                          n_jobs=-1)

            clf2 = ExtraTreesClassifier(max_depth=classifier_info['max_depth'],
                                        n_estimators=classifier_info['trees'],
                                        max_features=classifier_info['rand_vars'],
                                        min_samples_split=classifier_info['min_samps'],
                                        n_jobs=-1)

            clf3 = SVC(gamma=classifier_info['gamma'], C=classifier_info['C'])

            clf4 = GaussianNB()

            clf1.fit(self.p_vars, self.labels)
            clf2.fit(self.p_vars, self.labels)

            if locate_outliers:

                weights = np.ones(len(self.labels))
                for c, curr_c_idx in viewitems(self.class_outliers):

                    class_idx = np.where(self.labels == c)

                    weights[class_idx][curr_c_idx] *= 10

            else:
                weights = None

            clf3.fit(self.p_vars, self.labels, sample_weight=weights)

            clf4.fit(self.p_vars, self.labels)

            ## plot the dataset first
            ax1 = plt.subplot(221)
            ax2 = plt.subplot(222)
            ax3 = plt.subplot(223)
            ax4 = plt.subplot(224)

            ax1.set_xlim(xx.min(), xx.max())
            ax1.set_ylim(yy.min(), yy.max())
            ax1.set_xticks(())
            ax1.set_yticks(())

            ax2.set_xlim(xx.min(), xx.max())
            ax2.set_ylim(yy.min(), yy.max())
            ax2.set_xticks(())
            ax2.set_yticks(())

            ax3.set_xlim(xx.min(), xx.max())
            ax3.set_ylim(yy.min(), yy.max())
            ax3.set_xticks(())
            ax3.set_yticks(())

            ax4.set_xlim(xx.min(), xx.max())
            ax4.set_ylim(yy.min(), yy.max())
            ax4.set_xticks(())
            ax4.set_yticks(())

            ## plot the decision boundary
            if hasattr(clf1, 'decision_function'):
                Z1 = clf1.decision_function(np.c_[xx.ravel(), yy.ravel()])[:, class2check-1]
            else:
                Z1 = clf1.predict_proba(np.c_[xx.ravel(), yy.ravel()])[:, class2check-1]

            if hasattr(clf2, 'decision_function'):
                Z2 = clf2.decision_function(np.c_[xx.ravel(), yy.ravel()])[:, class2check-1]
            else:
                Z2 = clf2.predict_proba(np.c_[xx.ravel(), yy.ravel()])[:, class2check-1]

            if hasattr(clf3, 'decision_function'):
                Z3 = clf3.decision_function(np.c_[xx.ravel(), yy.ravel()])[:, class2check-1]
            else:
                Z3 = clf3.predict_proba(np.c_[xx.ravel(), yy.ravel()])[:, class2check-1]

            if hasattr(clf4, 'decision_function'):
                Z4 = clf4.decision_function(np.c_[xx.ravel(), yy.ravel()])[:, class2check-1]
            else:
                Z4 = clf4.predict_proba(np.c_[xx.ravel(), yy.ravel()])[:, class2check-1]

            # Put the result into a color plot
            Z1 = Z1.reshape(xx.shape)
            ax1.contourf(xx, yy, Z1, cmap=cm, alpha=.8)

            Z2 = Z2.reshape(xx.shape)
            ax2.contourf(xx, yy, Z2, cmap=cm, alpha=.8)

            Z3 = Z3.reshape(xx.shape)
            ax3.contourf(xx, yy, Z3, cmap=cm, alpha=.8)

            Z4 = Z4.reshape(xx.shape)
            ax4.contourf(xx, yy, Z4, cmap=cm, alpha=.8)

        leg_items = []
        leg_names = []

        for n_class in range(0, self.n_classes):

            cl_idx = np.where(self.labels == self.classes[n_class])

            # plot the training points
            curr_pl = ax1.scatter(self.p_vars[:, 0][cl_idx], self.p_vars[:, 1][cl_idx],
                                 c=colors[n_class], alpha=.7)#, cmap=cm_bright)

            ax2.scatter(self.p_vars[:, 0][cl_idx], self.p_vars[:, 1][cl_idx],
                                 c=colors[n_class], alpha=.7)#, cmap=cm_bright)

            if compare == 2:

                ax3.scatter(self.p_vars[:, 0][cl_idx], self.p_vars[:, 1][cl_idx],
                            c=colors[n_class], alpha=.7)#, cmap=cm_bright)

                ax4.scatter(self.p_vars[:, 0][cl_idx], self.p_vars[:, 1][cl_idx],
                            c=colors[n_class], alpha=.7)#, cmap=cm_bright)

            leg_items.append(curr_pl)
            leg_names.append(str(self.classes[n_class]))

        if compare == 1:

            if 'rf' in classifier_info['classifier']:

                ax1.set_xlabel('RF, Max. depth: %d' % classifier_info['max_depth'])
                ax2.set_xlabel('Extreme RF, Max. depth: %d' % classifier_info['max_depth'])

            elif classifier_info['classifier'] == 'SVM':

                ax1.set_xlabel('C: %d' % classifier_info['C'])
                ax2.set_xlabel('C: %d' % C2)

        else:

            ax1.set_xlabel('Random Forest')
            ax2.set_xlabel('Extremely Random Forest')
            ax3.set_xlabel('SVM')
            ax4.set_xlabel('Naives Bayes')

        plt.show()

        plt.close()

    def vis_series(self, class_list=[], class_names={}, smooth=True, window_size=3, xaxis_labs=[],
                   show_intervals=True, show_raw=False):

        """
        Visualize classes in a time series

        Args:
            class_list (Optional[list]): A list of classes to compare. Default is [], or all classes.
            class_names (Optional[dict]): A dictionary of class names. Default is {}, so the labels
                are the class values.
            smooth (Optional[bool]): Whether to smooth the time series. Default is True.
            window_size (Optional[int]): The window size to use for smoothing. Default is 3.
            xaxis_labs (Optional[str list]): A list of labels for the x-axis. Default is [].
            show_intervals (Optional[bool]): Whether to fill axis intervals. Default is True.
            show_raw (Optional[bool]): Whether to plot the raw data points. Default is False.

        Examples:
            >>> import mpglue as gl
            >>>
            >>> cl = gl.classification()
            >>>
            >>> cl.split_samples('/samples.txt', classes2remove=[1, 4],
            >>>                  class_subs={2:.1, 5:.01, 8:.1, 9:.9})
            >>> cl.vis_series(1, class_list=[3, 5, 8],
            >>>               class_names={3: 'forest', 5: 'agriculture', 8: 'water'})
        """

        fig = plt.figure(facecolor='white')

        ax = fig.add_subplot(111, axisbg='white')

        mpl.rcParams['font.size'] = 12.
        mpl.rcParams['font.family'] = 'Verdana'
        mpl.rcParams['axes.labelsize'] = 8.
        mpl.rcParams['xtick.labelsize'] = 8.
        mpl.rcParams['ytick.labelsize'] = 8.

        # new x values
        xn_ax = np.linspace(0, self.n_feas-1, (self.n_feas-1)*10)

        colors = ['black', 'cyan', 'yellow', 'red', 'orange', 'green', 'purple', 'magenta', '#5F4C0B', '#21610B',
                  '#210B61']

        if not class_list:
            class_list = self.classes

        ## setup the class names
        ## we might not have all the classes in the current samples
        class_names_list = [class_names[cl] for cl in class_list]

        # self.df = pd.DataFrame(np.zeros((0, self.n_feas)))

        leg_items = []
        for n_class, class_name in enumerate(class_names_list):

            # get the current class array indices
            cl_idx = np.where(self.labels == self.classes[n_class])

            idx2del = []
            for ri, r in enumerate(self.p_vars[cl_idx]):
                if r.max() == 0:
                    idx2del.append(ri)

            if idx2del:
                vis_p_vars = np.delete(self.p_vars[cl_idx], idx2del, axis=0)
            else:
                vis_p_vars = np.copy(self.p_vars[cl_idx])

            # df_sm = self.pd_interpolate(vis_p_vars.astype(np.float32), window_size)
            # the_nans, x = self.nan_helper(vis_p_vars)
            # df_sm = self.lin_interp2(x, y, the_nans)

            # idx = np.arange(vis_p_vars.shape[1])
            # df_sm = np.apply_along_axis(self.lin_interp, 1, vis_p_vars.astype(np.float32), idx)

            # vis_p_vars[vis_p_vars == 0] = np.nan
            df_sm = _lin_interp.lin_interp(vis_p_vars.astype(np.float32))

            df_sm = _rolling_stats.rolling_stats(df_sm, stat='median', window_size=window_size)

            df_sm_std = df_sm.std(axis=1)
            df_sm_u = df_sm.mean(axis=1)
            df_sm_up = df_sm_u + (1.5 * df_sm_std)
            df_sm_um = df_sm_u - (1.5 * df_sm_std)

            for idx_check in range(0, 2):

                idx = np.where((df_sm[:, idx_check] > df_sm_up) | (df_sm[:, idx_check] < df_sm_um))

                if len(idx[0]) > 0:

                    df_sm[:, idx_check][idx] = np.median(df_sm[:, :3][idx], axis=1)

            for idx_check in range(self.n_feas-1, self.n_feas-3, -1):

                idx = np.where((df_sm[:, idx_check] > df_sm_up) | (df_sm[:, idx_check] < df_sm_um))

                if len(idx[0]) > 0:

                    df_sm[:, idx_check][idx] = np.median(df_sm[:, :3][idx], axis=1)

            df_sm_u = np.nanmean(df_sm, axis=0)
            df_sm_std = np.nanstd(df_sm, axis=0)

            if smooth:

                df_sm_u_int = interp1d(range(self.n_feas), df_sm_u, kind='cubic')
                df_sm_std_int = interp1d(range(self.n_feas), df_sm_std, kind='cubic')

            # add the class index
            # df_sm.index = [class_name]*df_sm.shape[0]

            # self.df = self.df.append(df_sm)
            marker_size = .1
            line_width = 1.5
            alpha = .5

            for r in range(0, df_sm.shape[0]):

                if show_raw:

                    # raw data
                    ax.scatter(range(len(vis_p_vars[r])), vis_p_vars[r], marker='o', edgecolor='none', s=40,
                               facecolor=colors[n_class], c=colors[n_class])

                # new y values
                if smooth:
                    yn_cor = interp1d(range(self.n_feas), df_sm[r, :], kind='cubic')

                ## Savitsky Golay filtered
                # ax.plot(range(len(df_sm_sav[r])), df_sm_sav[r], marker='o', markeredgecolor='none', markersize=5,
                #          markerfacecolor=colors[-1], c=colors[-1], alpha=.7, lw=2)

                    ## Cubic interpolation
                    ax.plot(xn_ax, yn_cor(xn_ax), marker='o', markeredgecolor='none', markersize=marker_size,
                             markerfacecolor=colors[n_class], linestyle='-', c=colors[n_class], alpha=alpha,
                             lw=line_width)

                else:

                    ## raw data
                    ax.plot(range(len(df_sm[r])), df_sm[r], marker='o', markeredgecolor='none',
                            markersize=marker_size, markerfacecolor=colors[-2], linestyle='-', c=colors[n_class],
                            alpha=alpha, lw=line_width)

            if smooth:

                yn_cor = interp1d(range(self.n_feas), df_sm[-1, :], kind='cubic')

                dummy = ax.scatter(xn_ax, yn_cor(xn_ax), marker='o', edgecolor='none', s=marker_size,
                                 facecolor=colors[n_class], c=colors[n_class], alpha=alpha, lw=line_width,
                                 label=class_name)

                if show_intervals:

                    ax.fill_between(xn_ax, df_sm_u_int(xn_ax)-(2*df_sm_std_int(xn_ax)),
                                     df_sm_u_int(xn_ax)+(2*df_sm_std_int(xn_ax)), color=colors[n_class], alpha=.1)

            else:

                dummy = ax.scatter(range(len(df_sm[r])), df_sm[r], marker='o', edgecolor='none', s=marker_size,
                                 facecolor=colors[n_class], c=colors[n_class], alpha=alpha, lw=line_width,
                                 label=class_name)

                if show_intervals:

                    ax.fill_between(range(len(df_sm_u)), df_sm_u-(2*df_sm_std), df_sm_u+(2*df_sm_std),
                                    color=colors[n_class], alpha=.1)

            leg_items.append(dummy)

            plt.ylabel('Value')
            # plt.ylabel('Feature: %d' % fea_2)

            # ax.set_xlabel('Feature: %d')
            # ax.set_ylabel('Feature: %d' % fea)

        limits = False

        leg = plt.legend(tuple(leg_items), tuple(class_names_list), scatterpoints=1, loc='lower left',
                         markerscale=marker_size*200)

        leg.get_frame().set_edgecolor('#D8D8D8')
        leg.get_frame().set_linewidth(.5)

        if xaxis_labs:

            ax.set_xticks(range(self.n_feas))
            ax.set_xticklabels(xaxis_labs)

        plt.xlim(0, self.n_feas)
        plt.ylim(50, 250)

        plt.setp(plt.xticks()[1], rotation=30)

        plt.tight_layout()

        plt.show()

        plt.close(fig)

    # def lin_interp(self, in_block, indices):
    #
    #     in_block[in_block == 0] = np.nan
    #
    #     not_nan = np.logical_not(np.isnan(in_block))
    #
    #     return np.interp(indices, indices[not_nan], in_block[not_nan]).astype(np.float32)

    # def pd_interpolate(self, in_block, window_size):
    #
    #     in_block[in_block == 0] = np.nan
    #
    #     df = pd.DataFrame(in_block)
    #
        # linear interpolation along the x axis (layers)
        # df = df.apply(pd.Series.interpolate, axis=1).values.astype(np.float32)
        # df = df.apply(pd.Series.interpolate, axis=1)

        # rolling mean along the x axis and converted to ndarray
        # df = pd.rolling_median(df, window=window_size, axis=1).values
        # df = mp.rolling_stats(df, stat='median', window_size=window_size)

        # # fill the first two columns
        # if window_size == 3:
        #
        #     # df[:, 0] = np.median(df[:, :window_size-1], axis=1)
        #     # df[:, 1] = np.median(df[:, :window_size], axis=1)
        #     # df[:, -1] = np.median(df[:, -window_size:], axis=1)
        #     # df[:, -2] = np.median(df[:, -window_size-1:], axis=1)
        #
        #     df[:, 0] = np.median(df[:, :window_size-1+(window_size/2)], axis=1)
        #     df[:, 1] = np.median(df[:, :window_size+(window_size/2)], axis=1)
        #     df[:, -1] = np.median(df[:, -window_size-(window_size/2):], axis=1)
        #     df[:, -2] = np.median(df[:, -window_size-1-(window_size/2):], axis=1)
        #
        # elif window_size == 5:
        #
        #     df[:, 0] = np.median(df[:, :window_size-3+(window_size/2)], axis=1)
        #     df[:, 1] = np.median(df[:, :window_size-2+(window_size/2)], axis=1)
        #     df[:, 2] = np.median(df[:, :window_size-1+(window_size/2)], axis=1)
        #     df[:, 3] = np.median(df[:, :window_size+(window_size/2)], axis=1)
        #
        #     df[:, -1] = np.median(df[:, -window_size-(window_size/2):], axis=1)
        #     df[:, -2] = np.median(df[:, -window_size-1-(window_size/2):], axis=1)
        #     df[:, -3] = np.median(df[:, -window_size-2-(window_size/2):], axis=1)
        #     df[:, -4] = np.median(df[:, -window_size-3-(window_size/2):], axis=1)

        # df[np.isnan(df)] = 0

        # return np.apply_along_axis(savgol_filter, 1, df, 5, 3)
        # return df

    def vis_k_means(self, image, bands2vis=[1, 2, 3], clusters=3):

        """
        Use k-means clustering to visualize data in image

        Args:
            image (str): The image to visualize.
            bands2vis (Optional[int list]): A list of bands to visualize. Default is [1, 2, 3].
            clusters (Optional[int]): The number of clusters. Default is 3.
        """

        # open the image
        with raster_tools.ropen(image) as i_info:
            band_arrays = [zoom(i_info.read(bands2open=[bd], d_type='float32'), .5) for bd in bands2vis]

        rws, cls = band_arrays[0].shape[0], band_arrays[1].shape[1]

        ## reshape the arrays
        multi_d = np.empty((len(bands2vis), rws, cls)).astype(np.float32)

        ctr = 0
        for n in range(len(bands2vis)):

            multi_d[ctr] = band_arrays[n]

            ctr += 1

        multi_d = multi_d.reshape((len(bands2vis), rws*cls)).astype(np.float32).T

        # run k means clustering
        clt = KMeans(max_iter=300, n_jobs=-1, n_clusters=clusters)
        clt.fit(multi_d)

        hst = self._centroid_histogram(clt)

        bar = self._plot_colors(hst, clt.cluster_centers_)

        plt.figure()
        plt.axis('off')
        plt.imshow(bar)
        plt.show()

        plt.close()

    def _centroid_histogram(self, clt):

        # grab the number of different clusters and create a histogram
        # based on the number of pixels assigned to each cluster
        n_labels = np.arange(0, len(np.unique(clt.labels_) + 1))
        hist, _ = np.histogram(clt.labels_, bins=n_labels)

        # normalize the histogram, such that it sums to one
        hist = hist.astype('float')
        hist /= hist.sum()

        return hist

    def _plot_colors(self, hist, centroids):

        # initialize the bar chart representing the relative frequency of each of the colors
        bar = np.zeros((50, 300, 3), dtype='uint8')
        start_x = 0

        # iterate over the percentage of each cluster and the color of each cluster
        for (percent, color) in zip(hist, centroids):

            # plot the relative percentage of each cluster
            end_x = start_x + (percent * 300)

            cv2.rectangle(bar, (int(start_x), 0), (int(end_x), 50), color.astype('uint8').tolist(), -1)

            start_x = end_x

        return bar


class Preprocessing(object):

    """A class for data preprocessing"""

    def __init__(self):
        self.time_stamp = time.asctime(time.localtime(time.time()))

    def compare_features(self, f1, f2, method='mahalanobis'):

        """
        Compares features (within samples) using distance-based methods

        Args:
            f1 (int): The first feature position to compare.
            f2 (int): The second feature position to compare.
            method (Optional[str]): The distance method to use. Default is 'mahalanobis'.
        """

        dist_methods = dict(mahalanobis=sci_dist.mahalanobis,
                            correlation=sci_dist.correlation,
                            euclidean=sci_dist.euclidean)

        if method == 'mahalanobis':

            return dist_methods[method](self.p_vars[f1-1], self.p_vars[f2-1], np.linalg.cov(self.p_vars[f1-1],
                                                                                            self.p_vars[f2-1],
                                                                                            rowvar=0))

        else:
            return dist_methods[method](self.p_vars[f1-1], self.p_vars[f2-1])

    def compare_samples(self, base_samples, compare_samples, output, id_label='Id', y_label='Y',
                        response_label='response', dist_threshold=500, pct_threshold=.75,
                        replaced_weight=2, semi_supervised=False, spatial_weights=False, add2base=False):

        """
        Compares features (between samples) and removes samples

        Args:
            base_samples (str): The baseline samples.
            compare_samples (str): The samples to compare to the baseline, ``base_samples``.
            output (str): The output (potentially reduced) samples.
            id_label (Optional[str]): The id label. Default is 'Id'.
            y_label (Optional[str]): The Y label. Default is 'Y'.
            response_label (Optional[str]): The response (or class outcome) label. Default is 'response'.
            dist_threshold (Optional[int]): The euclidean distance threshold, where samples with distance
                values above `dist_threshold` are removed. Default is 300.
            pct_threshold (Optional[float]): The proportional number of image variables required
                above 'pct_threshold`. Default is 0.75.
            replaced_weight (Optional[int or float]): The weight value to add to new samples. Default is 2.
            semi_supervised (Optional[bool]): Whether to apply semi-supervised learning to the
                unselected samples. Default is False.
            spatial_weights (Optional[bool]): Whether to apply inverse spatial weights. Default is False.
            add2base (Optional[bool]): Whether to add the samples to the baseline set. Default is False.

        Example:
            >>> compare_samples('/2000.txt', '/2014.txt', '/2014_mod.csv')

        Explained:
            1) Get the euclidean distance between image variables.

        Returns:
            None, writes to ``output``.
        """

        weights = None

        df_base = pd.read_csv(base_samples, sep=',')
        df_compare = pd.read_csv(compare_samples, sep=',')

        # Load sample weights.
        if os.path.isfile(base_samples.replace('.txt', '_w.txt')):

            weights = PickleIt.load(base_samples.replace('.txt', '_w.txt'))

            if isinstance(weights, list):
                weights = np.array(weights, dtype='float32')

        # Reset the ids in case of stacked samples.
        df_base[id_label] = list(range(1, df_base.shape[0] + 1))
        df_compare[id_label] = list(range(1, df_compare.shape[0] + 1))

        all_headers = df_base.columns.values.tolist()

        leaders = all_headers[all_headers.index(id_label):all_headers.index(y_label) + 1]

        headers = all_headers[all_headers.index(y_label) + 1:all_headers.index(response_label)]

        added_headers = ('_y,'.format(headers[0]).join(headers) + '_y').split(',')

        df_base.rename(columns=dict(zip(headers, added_headers)), inplace=True)

        if isinstance(weights, np.ndarray):

            df_base['WEIGHT'] = weights

            df = pd.merge(df_compare, df_base[[id_label] + added_headers + ['WEIGHT']], on=id_label, how='inner')

        else:
            # Merge column-wise, with 'compare samples' first, then 'base samples'
            df = pd.merge(df_compare, df_base[[id_label] + added_headers], on=id_label, how='inner')

        if spatial_weights:

            self.index_samples(df.query('WEIGHT == 1'))

            dist_weights = self.weight_samples(df.query('WEIGHT == 1'), df.query('WEIGHT != 1'))

            # Calculate the inverse distance
            df.loc[df['WEIGHT'] != 1, 'WEIGHT'] = 1. - (dist_weights['SP_DIST'] / dist_weights['SP_DIST'].max())

        def e_dist(d, h1, h2):
            return (d[h1] - d[h2]) ** 2.

        df['COUNT'] = 0

        # Iterate over each image variable and
        #   calculate the euclidean distance.
        for compare_header, base_header in zip(headers, added_headers):

            df['DIST'] = e_dist(df, compare_header, base_header)

            df.loc[df['DIST'] < dist_threshold, 'COUNT'] += 1

        if semi_supervised:

            # Add unlabeled values to samples with high distance values.
            df.loc[df['COUNT'] < int(pct_threshold * len(headers)), 'response'] = -1

            # Semi-supervised learning.
            label_spread = label_propagation.LabelSpreading(kernel='rbf')
            label_spread.fit(df[headers], df['response'])

            # Replace the high distance samples' unlabeled responses.
            df.loc[df['COUNT'] < int(pct_threshold * len(headers)), 'response'] = label_spread.transduction_

        else:
            df = df.query('COUNT >= {:d}'.format(int(pct_threshold * len(headers))))

        # Copy the 'base samples' weights and add new weights
        if isinstance(weights, np.ndarray):

            weights_out = df['WEIGHT'].values
            weights_out = np.where(weights_out == 1, replaced_weight, weights_out)

        # Get the 'compare sample' image variables.
        df = df[leaders + headers + ['response']]

        if add2base:

            # Add the original column names back.
            df_base = df_base.rename(columns=dict(zip(added_headers, headers)))[leaders + headers + ['response']]

            # Concatenate the base samples with the new samples.
            df = pd.concat([df_base, df], axis=0)

            if isinstance(weights, np.ndarray):

                # Concatenate the base weights with the new weights.
                weights_out = np.concatenate([weights, weights_out], axis=0)

                assert df.shape[0] == len(weights_out)

        logger.info('  Base samples: {:,d}'.format(df_base.shape[0]))
        logger.info('  New samples: {:,d}'.format(df.shape[0]))

        if os.path.isfile(output):
            os.remove(output)

        df.to_csv(output, sep=',', index=False)

        if os.path.isfile(base_samples.replace('.txt', '_w.txt')):

            if os.path.isfile(compare_samples.replace('.txt', '_w.txt')):
                os.remove(compare_samples.replace('.txt', '_w.txt'))

            PickleIt.dump(weights_out, compare_samples.replace('.txt', '_w.txt'))

    def _index_samples(self, base_samples, x_label='X', y_label='Y'):

        """
        Indexes samples into a RTree database

        Args:
            base_samples (DataFrame): It should only contain 'good' points.
        """

        self.rtree_index = rtree.index.Index(interleaved=False)

        # Iterate over each sample.
        for di, df_row in base_samples.iterrows():

            x = float(df_row[x_label])
            y = float(df_row[y_label])

            self.rtree_index.insert(int(df_row['UNQ']), (x, y))

    def weight_samples(self,
                       df_samples,
                       base_query,
                       compare_query,
                       id_label='Id',
                       x_label='X',
                       y_label='Y',
                       w_label='WEIGHT'):

        """
        Weights samples by inverse euclidean distance

        Assumptions:
            The input dataframe (`df_samples`) should have columns for X and Y coordinates, id labels,
            and predefined weights.

        Args:
            df_samples (Pandas DataFrame): The samples.
            base_query (str)
            compare_query (str)
            id_label (Optional[str]): The id column header.
            x_label (Optional[str]): The x coordinate column header.
            y_label (Optional[str]): The y coordinate column header.
            w_label (Optional[str]): The weights column header.

        Examples:
            >>> import mpglue as gl
            >>>
            >>> cl = gl.classification()
            >>>
            >>> # print(df.head())
            >>> #  X,  Y,  Id,  WEIGHT
            >>> # [x,  y,  l,   w]
            >>> # where,
            >>> #   WEIGHT is a predefined weight for each sample.
            >>>
            >>> # Get spatial weights.
            >>> df = cl.weight_samples(df, 'WEIGHT == 1', 'WEIGHT != 1')
        """

        base_samples = df_samples.query(base_query)
        compare_samples = df_samples.query(compare_query)

        base_samples['UNQ'] = list(range(0, base_samples.shape[0]))
        compare_samples['UNQ'] = list(range(0, compare_samples.shape[0]))

        # Create a RTree indexer.
        self._index_samples(base_samples,
                            id_label=id_label,
                            x_label=x_label,
                            y_label=y_label)

        sp_dists = list()

        # Iterate over each sample.
        for di, df_row in compare_samples.iterrows():

            # Get the x and y coordinates.
            x1 = float(df_row[x_label])
            y1 = float(df_row[y_label])

            # Get the nearest sample.
            n_sample_id = list(self.rtree_index.nearest((x1, y1), 1))

            # Get the base sample x and y coordinates.
            x2 = float(base_samples.loc[base_samples['UNQ'] == n_sample_id[0], x_label])
            y2 = float(base_samples.loc[base_samples['UNQ'] == n_sample_id[0], y_label])

            # Calculate the euclidean distance
            #   between the two samples.
            sp_dists.append(sci_dist.euclidean([x1, y1], [x2, y2]))

        compare_samples['SP_DIST'] = sp_dists

        df_samples.loc[df_samples[w_label] != 1, w_label] = \
            1. - (compare_samples['SP_DIST'] / compare_samples['SP_DIST'].max())

        return df_samples

    def remove_outliers(self, outliers_fraction=.25, locate_only=False):

        """
        Removes outliers from each class by fitting an Elliptic Envelope

        Args:
            outliers_fraction (Optional[float]): The proportion of outliers. Default is .25.
            locate_only (Optional[bool]): Whether to locate and do not remove outliers. Default is False.

        Examples:
            >>> import mpglue as gl
            >>>
            >>> cl = gl.classification()
            >>>
            >>> # Get predictive variables and class labels data.
            >>>
            >>> # The data should be scaled, as the the Elliptic Envelope
            >>> #   assumes a Gaussian distribution
            >>> cl.split_samples('/samples.txt', perc_samp=1., scale_data=True)
            >>>
            >>> # Search for outliers in the sample data
            >>> #   the new p_vars are stored in the <cl> instance.
            >>> cl.remove_outliers()
            >>>
            >>> # Check the outlier locations
            >>> print cl.class_outliers
        """

        if not self.scaled:

            logger.error('  The data should be scaled prior to outlier removal.')
            raise NameError

        self.outliers_fraction = outliers_fraction

        # xx, yy = np.meshgrid(np.linspace(-7, 7, self.n_samps*self.n_feas),
        #                      np.linspace(-7, 7, self.n_samps*self.n_feas))

        new_p_vars = np.empty((0, self.n_feas), dtype='float32')
        new_labels = np.array([], dtype='int16')

        self.class_outliers = {}

        for check_class in self.classes:

            logger.info('  Class {:d} ...'.format(check_class))

            try:
                new_p_vars, new_labels = self._remove_outliers(check_class, new_p_vars, new_labels)
            except:
                logger.error('  Could not fit the data for class {:d}'.format(check_class))
                raise RuntimeError

        if not locate_only:

            self.p_vars = new_p_vars
            self.labels = new_labels

            self.update_class_counts()

    @retry(wait_random_min=500, wait_random_max=1000, stop_max_attempt_number=5)
    def _remove_outliers(self, check_class, new_p_vars, new_labels):

        # row indices for current class
        class_idx = np.where(self.labels == check_class)

        temp_p_vars = self.p_vars[class_idx]
        temp_labels = self.labels[class_idx]

        # outlier detection
        outlier_clf = EllipticEnvelope(contamination=.1)

        try:
            outlier_clf.fit(temp_p_vars)
        except:

            new_p_vars = np.vstack((new_p_vars, self.p_vars_original[class_idx]))
            new_labels = np.concatenate((new_labels, temp_labels))

            return new_p_vars, new_labels

        y_pred = outlier_clf.decision_function(temp_p_vars).ravel()

        threshold = stats.scoreatpercentile(y_pred, 100. * self.outliers_fraction)

        inlier_idx = np.where(y_pred >= threshold)
        outlier_idx = np.where(y_pred < threshold)

        self.class_outliers[check_class] = outlier_idx

        n_outliers = len(y_pred) - len(inlier_idx[0])

        logger.info('  {:d} outliers in class {:d}'.format(n_outliers, check_class))

        # temp_p_vars = temp_p_vars[inlier_idx]

        temp_labels = temp_labels[inlier_idx]

        # update the features
        new_p_vars = np.vstack((new_p_vars, self.p_vars_original[class_idx][inlier_idx]))

        # update the labels
        new_labels = np.concatenate((new_labels, temp_labels))

        return new_p_vars, new_labels

    def semi_supervised(self,
                        label_method='propagate',
                        var_array=None,
                        lab_array=None,
                        sub_idx=None,
                        **kwargs):

        """
        Predict class values of unlabeled samples

        Args:
            label_method (Optional[str]): The semi-supervised label method. Default is 'propagate'. Choices
                are ['propagate', 'spread'].
            var_array (Optional[2d array]): An array to replace `self.p_vars`. Default is None.
            lab_array (Optional[1d array]): An array to replace `self.labels`. Default is None.
            sub_idx (Optional[1d array-like]): A list or array of indices to subset by. Default is None.
            kwargs (Optional[dict]): Keyword arguments to be passed to the semi-supervised method.

        Examples:
            >>> # create the classifier object
            >>> import mpglue as gl
            >>>
            >>> cl = gl.classification()
            >>>
            >>> # get predictive variables and class labels data, sampling 100%
            >>> # the unknown samples should have a class value of -1
            >>> cl.split_samples('/samples.txt', perc_samp=1.)
            >>>
            >>> # run semi-supervised learning to predict unknowns
            >>> # the instances <labels>, <classes>, <n_classes>,
            >>> # and <class_counts> are updated
            >>> cl.semi_supervised()
        """

        if isinstance(sub_idx, np.ndarray) or isinstance(sub_idx, list):

            if isinstance(var_array, np.ndarray):

                var_array = var_array[np.array(sorted(sub_idx), dtype='int64')]
                lab_array = lab_array[np.array(sorted(sub_idx), dtype='int64')]

            else:

                var_array = self.p_vars[np.array(sorted(sub_idx), dtype='int64')]
                lab_array = self.labels[np.array(sorted(sub_idx), dtype='int64')]

        else:

            if not isinstance(var_array, np.ndarray):

                var_array = self.p_vars
                lab_array = self.labels

        unlabeled_idx = np.where(lab_array == -1)

        if label_method == 'propagate':
            ss_model = label_propagation.LabelPropagation(**kwargs)
        else:
            ss_model = label_propagation.LabelSpreading(**kwargs)

        ss_model.fit(var_array, lab_array)

        lab_array[unlabeled_idx] = ss_model.transduction_[unlabeled_idx]

        return lab_array

        # self.update_class_counts()

        # the model parameters
        # self._default_parameters()
        #
        # if classifier_info['classifier'] == 'rf':
        #
        #     label_spread = ensemble.RandomForestClassifier(max_depth=classifier_info['max_depth'],
        #                                                    n_estimators=classifier_info['trees'],
        #                                                    max_features=classifier_info['rand_vars'],
        #                                                    min_samples_split=classifier_info['min_samps'],
        #                                                    n_jobs=-1)
        #
        # elif classifier_info['classifier'] == 'ex-rf':
        #
        #     label_spread = ensemble.ExtraTreesClassifier(max_depth=classifier_info['max_depth'],
        #                                                  n_estimators=classifier_info['trees'],
        #                                                  max_features=classifier_info['rand_vars'],
        #                                                  min_samples_split=classifier_info['min_samps'],
        #                                                  n_jobs=-1)
        #
        # labeled_vars_idx = np.where(self.labels != -1)
        # labeled_vars = self.p_vars[labeled_vars_idx]
        # labels = self.labels[labeled_vars_idx]
        #
        # label_spread.fit(labeled_vars, labels)
        #
        # # keep the good labels
        # unknown_labels_idx = np.where(self.labels == -1)
        #
        # # predict the unlabeled
        # temp_labels = label_spread.predict(self.p_vars)
        #
        # # save the predictions of the unknowns
        # self.labels[unknown_labels_idx] = temp_labels[unknown_labels_idx]
        #
        # # update the individual class counts
        # self.classes = list(np.delete(self.classes, 0))
        # self.class_counts = {}
        # for indv_class in self.classes:
        #     self.class_counts[indv_class] = len(np.where(self.labels == indv_class)[0])
        #
        # self.n_classes = len(self.classes)


class ModelOptions(object):

    @staticmethod
    def model_options():

        return """\

        Supported models

        ===========================
        Parameter name -- Long name
                          *Module
        ===========================

        ab-dt       -- AdaBoost with CART (classification problems)
                        *Scikit-learn
        ab-ex-dt    -- AdaBoost with extremely random trees (classification problems)
                        *Scikit-learn
        ab-rf       -- AdaBoost with Random Forest (classification problems)
                        *Scikit-learn
        ab-ex-rf    -- AdaBoost with Extremely Random Forest (classification problems)
                        *Scikit-learn
        ab-dtr      -- AdaBoost with CART (regression problems)
                        *Scikit-learn
        ab-ex-dtr   -- AdaBoost with extremely random trees (regression problems)
                        *Scikit-learn
        bag-dt      -- Bagged Decision Trees (classification problems)
                        *Scikit-learn              
        bag-dtr     -- Bagged Decision Trees (regression problems)
                        *Scikit-learn            
        bag-ex-dt   -- Bagged Decision Trees with extremely randomized trees (classification problems)
                        *Scikit-learn
        blag        -- Resampled bagging (classification problems)
                        *Imbalanced-learn
        blaf        -- Resampled random forest (classification problems)
                        *Imbalanced-learn
        blab        -- Resampled boosting (classification problems)
                        *Imbalanced-learn                        
        bayes       -- Naives Bayes (classification problems)
                        *Scikit-learn
        dt          -- Decision Trees based on CART algorithm (classification problems)
                        *Scikit-learn
        dtr         -- Decision Trees Regression based on CART algorithm (regression problems)
                        *Scikit-learn
        ex-dt       -- Extra Decision Trees based on CART algorithm (classification problems)
                        *Scikit-learn
        ex-dtr      -- Extra Decision Trees Regression based on CART algorithm (regression problems)
                        *Scikit-learn                        
        catboost    -- CatBoost for Gradient Boosting (classification problems)
                        *Catboost        
        chaincrf    -- Linear-chain Conditional Random Fields (classification problems)
                        *Pystruct                        
        c5          -- C5 decision trees (classification problems)
                        {classifier:C5,trials:10,CF:.25,min_cases:2,winnow:False,no_prune:False,fuzzy:False}
        cubist      -- Cubist regression trees (regression problems)
                        {classifier:Cubist,committees:5,unbiased:False,rules:100,extrapolation:10}
        cvmlp       -- Feed-forward, artificial neural network, multi-layer perceptrons in OpenCV (classification problems)
                        {classifier:CVMLP}                        
        cvrf        -- Random Forests in OpenCV (classification problems)
                        {classifier:CVRF,trees:1000,min_samps:0,rand_vars:0,max_depth:25,weight_classes:None,truncate:False}                        
        cvsvm       -- Support Vector Machine in OpenCV (classification problems)
                        {classifier:CVSVM,C:1,g:1.0}
        cvsvma      -- Support Vector Machine, auto-tuned in OpenCV (classification problems)
                        {classifier:CVSVMA}
        cvsvmr      -- Support Vector Machine in OpenCV (regression problems)
                        {classifier:CVSVMR,C:1,g:1.0}
        cvsvmra     -- Support Vector Machine, auto-tuned in OpenCV (regression problems)
                        {classifier:CVSVMRA}                        
        ex-rf       -- Extremely Random Forests (classification problems)
                        *Scikit-learn
        ex-rfr      -- Extremely Random Forests (regression problems)
                        *Scikit-learn
        gaussian    -- Gaussian Process (classification problems)
                        *Scikit-learn
        gb          -- Gradient Boosted Trees (classification problems)
                        *Scikit-learn
        gbr         -- Gradient Boosted Trees (regression problems)
                        *Scikit-learn
        gridcrf     -- Pairwise Conditional Random Fields on a 2d grid (classification problems)
                        *Pystruct    
        lightgbm    -- Light Gradient Boosting (classification problems)
                        *LightGBM
        logistic    -- Logistic Regression (classification problems)
                        *Scikit-learn                        
        mondrian    -- Mondrian forests (classification problems)
                        *scikit-garden                        
        nn          -- K Nearest Neighbor (classification problems)
                        *Scikit-learn
        qda         -- Quadratic Discriminant Analysis (classification problems)
                        *Scikit-learn
        rf          -- Random Forests (classification problems)
                        *Scikit-learn                        
        rfr         -- Random Forests (regression problems)
                        *Scikit-learn
        svmc        -- C-support Support Vector Machine (classification problems)
                        {classifier:SVMc,C:1,kernel:'rbf',g:1/n_feas}
        svmcr       -- C-support Support Vector Machine (regression problems)
                        {classifier:SVMcR,C:1,g:1/n_feas}
        svmnu       -- Nu-support Support Vector Machine (classification problems)
                        {classifier:SVMnu,C:1,kernel:'rbf',g:1/n_feas}
        tpot        -- Tpot pipeline (classification problems)
                        *Tpot                                                
        xgboost     -- XGBoost for Gradient Boosting (classification problems)
                        *XGBoost                   
        """


class VotingClassifier(BaseEstimator, ClassifierMixin):

    """
    A voting classifier class to use prefit models instead of re-fitting

    Args:
        estimators (list of tuples): The fitted estimators.
        weights (Optional[list, 1d array-like): The estimator weights.
        y (1d array-like)
        classes (1d array-like)
    """

    def __init__(self, estimators, weights=None, y=None, classes=None):

        self.estimators = estimators
        self.weights = weights
        self.is_prefit_model = True
        self.y_ = y
        self.classes_ = None

        if isinstance(y, np.ndarray) or isinstance(y, list):
            self.classes_ = unique_labels(y)
        elif isinstance(classes, np.ndarray) or isinstance(classes, list):
            self.classes_ = classes

        if isinstance(self.weights, list):
            self.weights = np.array(self.weights, dtype='float32')

        if self.weights is None:
            self.weights = np.ones(len(self.estimators), dtype='float32')

        if len(self.weights) != len(self.estimators):

            logger.error('  The length of the weights must match the length of the estimators.')
            raise ArrayShapeError

        if isinstance(self.classes_, np.ndarray) or isinstance(self.classes_, list):
            self.n_classes_ = len(self.classes_)
        else:
            self.n_classes_ = 0

    def predict(self, X):

        """
        Predicts discrete classes by soft probability averaging

        Args:
            X (2d array): The predictive variables.
        """

        # Get predictions as an index of the array position.
        probabilities_argmax = np.argmax(self.predict_proba(X), axis=1)

        predictions = np.zeros(probabilities_argmax.shape, dtype='int16')

        # Convert indices to classes.
        for class_index, real_class in enumerate(self.classes_):
            predictions[probabilities_argmax == class_index] = real_class

        return predictions

    def predict_proba(self, X):

        """
        Predicts class posterior probabilities by soft probability averaging

        Args:
            X (2d array): The predictive variables.
        """

        clf = self.estimators[0][1]

        X_probas = clf.predict_proba(X) * self.weights[0]

        for clf_idx in range(1, len(self.estimators)):

            clf = self.estimators[clf_idx][1]
            X_probas += clf.predict_proba(X) * self.weights[clf_idx]

        return X_probas / self.weights.sum()


class classification(ModelOptions, PickleIt, Preprocessing, Samples, Visualization):

    """
    A class for image sampling and classification

    Example:
        >>> import mpglue as gl
        >>>
        >>> # Create the classification object.
        >>> cl = gl.classification()
        >>>
        >>> # Open land cover samples and split
        >>> #   into train and test datasets.
        >>> cl.split_samples('/samples.txt')
        >>>
        >>> # Add features
        >>> cl.add_features(['mean', 'cv'])
        >>>
        >>> # Train a Random Forest classification model.
        >>> # *Note that the model is NOT saved to file in
        >>> #   this example. However, the model IS passed
        >>> #   to the ``cl`` instance. To use the same model
        >>> #   after Python cleanup, save the model to file
        >>> #   with the ``output_model`` keyword. See the
        >>> #   ``construct_model`` function more details.
        >>> cl.construct_model(classifier_info={'classifier': 'rf',
        >>>                                     'trees': 1000,
        >>>                                     'max_depth': 25})
        >>>
        >>> # Apply the model to predict an entire image.
        >>> cl.predict('/image_variables.tif', '/image_labels.tif')
    """

    def __init__(self):
        self.time_stamp = time.asctime(time.localtime(time.time()))

    def copy(self):
        return copy(self)

    def construct_model(self,
                        input_model=None,
                        output_model=None,
                        classifier_info=None,
                        class_weight=None,
                        var_imp=True,
                        rank_method=None,
                        top_feas=0.5,
                        get_probs=False,
                        input_image=None,
                        in_shapefile=None,
                        out_stats=None,
                        stats_from_image=False,
                        calibrate_proba=False,
                        calibrate_test=None,
                        calibrate_labels=None,
                        calibrate_weights=None,
                        be_quiet=False,
                        compress_model=False,
                        view_calibration=None,
                        fig_location=None,
                        feature_list=None,
                        append_features=False,
                        ts_indices=None,
                        func_applier=None):

        """
        Loads, trains, and saves a predictive model.

        Args:
            input_model (Optional[str]): The input model name.
            output_model (Optional[str]): The output model name.
            classifier_info (Optional[dict]): A dictionary of classifier information. Default is {'classifier': 'rf'}.
            class_weight (Optional[bool]): How to weight classes for priors. Default is None. Choices are
                [None, 'percent', 'inverse'].
                *Example when class_weight=True:
                    IF
                        labels = [1, 1, 1, 2, 1, 2, 3, 2, 3]
                    THEN
                        class_weight = {1: .22, 2: .33, 3: .44}
            var_imp (Optional[bool]): Whether to return feature importance. Default is True.
            rank_method (Optional[str]): The rank method to use. 'chi2' or 'rf'. Default is None.
            top_feas (Optional[int or float]): The number or percentage of top ranked features to return.
                Default is .5, or 50%.
            get_probs (Optional[bool]): Whether to return class probabilities. Default is False.
            input_image (Optional[str]): An input image for Orfeo models. Default is None.
            in_shapefile (Optional[str]): An input shapefile for Orfeo models. Default is None.
            out_stats (Optional[str])
            output_stats (Optional[str]): A statistics file for Orfeo models. Default is None.
            stats_from_image (Optional[bool]): Whether to collect statistics from the image for Orfeo models. Default
                is False.
            calibrate_proba (Optional[bool]): Whether to calibrate posterior probabilities with a sigmoid
                calibration. Default is False.
            calibrate_test (Optional[2d array-like]): An array of test samples to use for model calibration. If None,
                self.p_vars_test and self.labels_test are used.
            calibrate_labels (Optional[1d array-like)]: An array of test labels to use for model calibration.
                The shape must match `calibrate_test` along the y-axis.
            calibrate_weights (Optional[1d array-like)]: An array of sample weights to use for model calibration.
                The shape must match `calibrate_test` along the y-axis.
            be_quiet (Optional[bool]): Whether to be quiet and do not print to screen. Default is False.
            compress_model (Optional[bool]): Whether to compress the model. Default is False.
            view_calibration (Optional[int]): View the calibrated probabilities of class `view_calibration`.
                Default is None.
            fig_location (Optional[str]): The location to save the `view_calibration` figure. Default is None.
            feature_list (Optional[str list]): A list of features to add to `p_vars`. Default is None.
                Choices are ['mean', 'cv'].
            append_features (Optional[bool]): Whether to append time series features to the existing features.
                Default is True.
            ts_indices (Optional[int list]): An index array for time series features. Default is None.
            func_applier (Optional[function]): A function to apply extra features. Default is None.

                E.g.,

                    def func_applier(x, self):
                        return np.concatenate((x, self.pca.transform(x)), axis=1)

        Examples:
            >>> # create the classifier object
            >>> import mpglue as gl
            >>>
            >>> cl = gl.classification()
            >>>
            >>> # get predictive variables and class labels data
            >>> cl.split_samples('/samples.txt')
            >>> # or
            >>> cl.split_samples('/samples.txt', classes2remove=[1, 4],
            >>>                  class_subs={2:.1, 5:.01, 8:.1, 9:.9})
            >>>
            >>> # train a Random Forest model
            >>> cl.construct_model(output_model='/test_model.txt',
            >>>                    classifier_info={'classifier': 'rf',
            >>>                                     'trees': 1000,
            >>>                                     'max_depth': 25})
            >>>
            >>> # or load a previously trained RF model
            >>> cl.construct_model(input_model='/test_model.txt')
            >>>
            >>> # use Orfeo to train a model
            >>> cl.construct_model(classifier_info={'classifier': 'OR_RF', 'trees': 1000,
            >>>                    'max_depth': 25, 'min_samps': 5, 'rand_vars': 10},
            >>>                    input_image='/image.tif', in_shapefile='/shapefile.shp',
            >>>                    out_stats='/stats.xml', output_model='/rf_model.xml')
            >>>
            >>> # or collect statistics from samples rather than the entire image
            >>> cl.construct_model(classifier_info={'classifier': 'OR_RF', 'trees': 1000,
            >>>                    'max_depth': 25, 'min_samps': 5, 'rand_vars': 10},
            >>>                    input_image='/image.tif', in_shapefile='/shapefile.shp',
            >>>                    out_stats='/stats.xml', output_model='/rf_model.xml',
            >>>                    stats_from_image=False)
        """

        self.input_model = input_model
        self.output_model = output_model
        self.var_imp = var_imp
        self.rank_method = rank_method
        self.top_feas = top_feas
        self.get_probs = get_probs
        self.compute_importances = None
        self.in_shapefile = in_shapefile
        self.out_stats = out_stats
        self.stats_from_image = stats_from_image
        self.input_image = input_image
        self.classifier_info = classifier_info
        self.calibrate_proba = calibrate_proba
        self.calibrate_test = calibrate_test
        self.calibrate_labels = calibrate_labels
        self.calibrate_weights = calibrate_weights
        self.class_weight = class_weight
        self.be_quiet = be_quiet
        self.compress_model = compress_model
        self.view_calibration = view_calibration
        self.fig_location = fig_location

        self.feature_object = None
        self._add_features = False
        self.calibrated = False
        self.feature_list = feature_list
        self.append_features = append_features
        self.ts_indices = ts_indices
        self.func_applier = func_applier

        if isinstance(self.view_calibration, int):

            if not isinstance(self.fig_location, str):

                logger.error('  The output figure location must be given with `view_calibration`.')
                raise TypeError

            if not os.path.isdir(self.fig_location):
                os.makedirs(self.fig_location)

        if isinstance(self.input_model, str):

            if not os.path.isfile(self.input_model):

                logger.exception('  {} does not exist.'.format(self.input_model))
                raise OSError

        if not isinstance(self.input_model, str):

            # check that the model is valid
            if 'classifier' not in self.classifier_info:

                logger.exception('  The model must be declared.')
                raise ValueError

            if not isinstance(self.classifier_info['classifier'], list):

                if self.classifier_info['classifier'] not in get_available_models():

                    logger.exception('  {} is not a model option.'.format(self.classifier_info['classifier']))
                    raise NameError

        if isinstance(self.output_model, str):

            d_name, f_name = os.path.split(self.output_model)
            f_base, f_ext = os.path.splitext(f_name)

            if not d_name and not os.path.isabs(f_name):
                d_name = os.path.abspath('.')

            self.out_acc = os.path.join(d_name, '{}_acc.txt'.format(f_base))

            if os.path.isfile(self.out_acc):
                os.remove(self.out_acc)

            if 'CV' in self.classifier_info['classifier']:

                if 'xml' not in f_ext.lower():

                    logger.error('  The output model for OpenCV models must be XML.')
                    raise TypeError

            if not os.path.isdir(d_name):
                os.makedirs(d_name)

        if isinstance(self.rank_method, str):
            self.compute_importances = True

        if isinstance(self.class_weight, str):

            class_proportions = OrderedDict()
            class_counts_ordered = OrderedDict(self.class_counts)

            # Get the proportion of samples for each class.
            for class_value in self.classes:
                class_proportions[class_value] = class_counts_ordered[class_value] / float(self.n_samps)

                # len(np.array(self.classes)[np.where(np.array(self.classes) == class_value)]) / float(len(self.classes))

            if self.class_weight == 'inverse':

                # rank self.class_counts from smallest to largest
                class_counts_ordered = OrderedDict(sorted(list(iteritems(class_counts_ordered)), key=lambda t: t[1]))

                # rank class_proportions from largest to smallest
                class_proportions = OrderedDict(sorted(list(iteritems(class_proportions)),
                                                       key=lambda t: t[1],
                                                       reverse=True))

                # swap the proportions of the largest class counts to the smallest

                self.class_weight = dict()

                for (k1, v1), (k2, v2) in zip(list(iteritems(class_counts_ordered)), list(iteritems(class_proportions))):
                    self.class_weight[k1] = v2

                if 'CV' in self.classifier_info['classifier']:
                    self.class_weight = np.array(itervalues(self.class_weight), dtype='float32')

            elif self.class_weight == 'percent':

                if 'CV' in self.classifier_info['classifier']:
                    self.class_weight = np.array(itervalues(class_proportions), dtype='float32')
                else:
                    self.class_weight = class_proportions

            else:
                logger.error('  The weight method is not supported.')
                raise NameError

        if isinstance(self.input_model, str):

            # Load the classifier parameters
            #   and the model.
            self._load_model()

            #   DB calcula accuracy, cuando se le da un modelo
            if isinstance(self.output_model, str):			
                self.test_accuracy(out_acc=self.out_acc)
            
        else:

            if self.feature_list:

                self.feature_object = TimeSeriesFeatures()
                self.feature_object.add_features(self.feature_list)

                if not self.ts_indices:

                    if self.use_xy:
                        self.ts_indices = np.array(range(0, self.p_vars.shape[1]-2), dtype='int64')

                # logger.info(self.p_vars.shape[1])
                # logger.info(self.p_vars_test.shape[1])
                # logger.info(self.calibrate_test.shape[1])
                # logger.info(ts_indices.shape)

                self.p_vars = self.feature_object.apply_features(X=self.p_vars,
                                                                 ts_indices=self.ts_indices,
                                                                 append_features=self.append_features)

                if isinstance(self.p_vars_test, np.ndarray):

                    self.p_vars_test = self.feature_object.apply_features(X=self.p_vars_test,
                                                                          ts_indices=self.ts_indices,
                                                                          append_features=self.append_features)

                if isinstance(self.calibrate_test, np.ndarray):

                    self.calibrate_test = self.feature_object.apply_features(X=self.calibrate_test,
                                                                             ts_indices=self.ts_indices,
                                                                             append_features=self.append_features)

                self._add_features = True

                self.sample_info_dict['n_feas'] = self.p_vars.shape[1]

            self.sample_info_dict['add_features'] = self._add_features
            self.sample_info_dict['feature_object'] = self.feature_object

            # Set the model parameters.
            self._default_parameters()

            # the model instance
            self._set_model()

            if self.classifier_info['classifier'] != 'ORRF':

                # get model parameters
                if not self.get_probs:
                    self._set_parameters()

                # train the model
                self._train_model()

    def _load_model(self):

        """Loads a previously saved model"""

        logger.info('  Loading {} ...'.format(self.input_model))

        if '.xml' in self.input_model:

            # first load the parameters
            try:
                self.classifier_info, __ = self.load(self.input_model)
            except:
                logger.error('  Could not load {}'.format(self.input_model))
                raise OSError

            # load the correct model
            self._set_model()

            # now load the model
            try:
                self.model.load(self.input_model)
            except:

                logger.error('  Could not load {}'.format(self.input_model))
                raise OSError

        else:

            # Scikit-learn models
            try:

                # self.classifier_info, self.model = self.load(self.input_model)
                self.classifier_info, self.model, self.sample_info_dict = joblib.load(self.input_model)

                self.n_feas = self.sample_info_dict['n_feas']
                self.scaler = self.sample_info_dict['scaler']
                self.scaled = self.sample_info_dict['scaled']
                self.use_xy = self.sample_info_dict['use_xy']
                self._add_features = self.sample_info_dict['add_features']
                self.feature_object = self.sample_info_dict['feature_object']

            except:
                logger.exception('  Could not load {}'.format(self.input_model))

    def _default_parameters(self):
        
        """Sets model parameters"""

        if isinstance(self.classifier_info['classifier'], list):
            return

        defaults_ = dict(n_estimators=100,
                         trials=10,
                         max_depth=25,
                         min_samples_split=2,
                         min_samples_leaf=5,
                         learning_rate=0.1,
                         C=1.0,
                         nu=0.5,
                         kernel='rbf',
                         n_jobs=-1)

        # Check if model parameters are set,
        #   otherwise, set defaults.

        if 'classifier' not in self.classifier_info:
            self.classifier_info['classifier'] = 'rf'

        # Models with base estimators
        if self.classifier_info['classifier'].startswith('ab-') or \
                self.classifier_info['classifier'].startswith('bag-') or \
                (self.classifier_info['classifier'] in ['blag', 'blab']):

            class_base = copy(self.classifier_info['classifier'])

            self.classifier_info['classifier'] = \
                self.classifier_info['classifier'][self.classifier_info['classifier'].find('-')+1:]

        else:
            class_base = 'none'

        vp = ParameterHandler(self.classifier_info['classifier'])

        # Check the parameters.
        self.classifier_info_ = copy(self.classifier_info)
        self.classifier_info_ = vp.check_parameters(self.classifier_info_, defaults_)

        # Create a separate instance for
        #   AdaBoost and Bagging base classifiers.
        if class_base.startswith('ab-') or class_base.startswith('bag-') or (class_base in ['blag', 'blab']):

            self.classifier_info_base = copy(self.classifier_info)
            self.classifier_info_base['classifier'] = class_base

            if 'trials' in self.classifier_info_base:

                self.classifier_info_base['n_estimators'] = self.classifier_info_base['trials']
                del self.classifier_info_base['trials']

            else:
                self.classifier_info_base['n_estimators'] = defaults_['trials']

            vp_base = ParameterHandler(self.classifier_info_base['classifier'])

            self.classifier_info_base = vp_base.check_parameters(self.classifier_info_base,
                                                                 defaults_,
                                                                 trials_set=True)

            if 'base_estimator' in self.classifier_info_base:
                del self.classifier_info_base['base_estimator']

            self.classifier_info['classifier'] = class_base

        # Random Forest in OpenCV
        if self.classifier_info['classifier'] == 'cvrf':

            if not self.input_model:

                # trees
                if 'trees' in self.classifier_info:
                    self.classifier_info['term_crit'] = (cv2.TERM_CRITERIA_MAX_ITER,
                                                         self.classifier_info['trees'], 0.1)
                else:
                    if 'term_crit' not in self.classifier_info:
                        self.classifier_info['term_crit'] = (cv2.TERM_CRITERIA_MAX_ITER, self.DEFAULT_TREES, 0.1)

                # minimum node samples
                if 'min_samps' not in self.classifier_info:
                    self.classifier_info['min_samps'] = int(np.ceil(0.01 * self.n_samps))

                # random features
                if 'rand_vars' not in self.classifier_info:
                    # sqrt of feature count
                    self.classifier_info['rand_vars'] = 0

                # maximum node depth
                if 'max_depth' not in self.classifier_info:
                    self.classifier_info['max_depth'] = self.DEFAULT_MAX_DEPTH

                if 'calc_var_importance' not in self.classifier_info:
                    self.classifier_info['calc_var_importance'] = 0

                if 'truncate' not in self.classifier_info:
                    self.classifier_info['truncate'] = False

                if 'priors' not in self.classifier_info:

                    if isinstance(self.class_weight, np.ndarray):
                        self.classifier_info['priors'] = self.class_weight
                    else:
                        self.classifier_info['priors'] = np.ones(self.n_classes, dtype='float32')

            # MLP
            elif self.classifier_info['classifier'] == 'cvmlp':

                if not self.input_model:

                    # hidden nodes
                    try:
                        __ = self.classifier_info['n_hidden']
                    except:
                        try:
                            self.classifier_info['n_hidden'] = (self.n_feas + self.n_classes) / 2
                        except:
                            logger.error('  Cannot infer number of hidden nodes.')
                            raise ValueError

        elif self.classifier_info['classifier'] in ['chaincrf', 'gridcrf']:

            if not PYSTRUCT_INSTALLED:

                logger.warning('  Pystruct must be installed to use CRF models.\nEnsure that pystruct and cvxopt are installed.')
                return

            if 'max_iter' not in self.classifier_info_:
                self.classifier_info_['max_iter'] = 1000

            if 'C' not in self.classifier_info_:
                self.classifier_info_['C'] = 0.001

            if 'n_jobs' not in self.classifier_info_:
                self.classifier_info_['n_jobs'] = -1

            if 'tol' not in self.classifier_info_:
                self.classifier_info_['tol'] = 0.001

            if 'inference_cache' not in self.classifier_info_:
                self.classifier_info_['inference_cache'] = 0

            if 'inference_method' not in self.classifier_info_:
                inference_method = 'qpbo'
            else:

                inference_method = self.classifier_info_['inference_method']
                del self.classifier_info_['inference_method']

            if 'neighborhood' not in self.classifier_info_:
                neighborhood = 4
            else:

                neighborhood = self.classifier_info_['neighborhood']
                del self.classifier_info_['neighborhood']

            self.grid_info = dict(inference_method=inference_method,
                                  neighborhood=neighborhood)

            # if 'break_on_bad' not in self.classifier_info_:
            #     self.classifier_info_['break_on_bad'] = True

            # self.classifier_info_['verbose'] = 1

    def _set_model(self):

        """Sets the model object"""

        # Create the model object.
        if isinstance(self.classifier_info['classifier'], list):

            self.discrete = True

            classifier_info = copy(self.classifier_info)

            classifier_list = list()

            ci = 0
            for classifier in classifier_info['classifier']:

                self.classifier_info = copy(classifier_info)
                self.classifier_info['classifier'] = classifier

                self._default_parameters()

                if classifier == 'bayes':
                    voting_sub_model = GaussianNB(**self.classifier_info_)

                elif classifier == 'nn':
                    voting_sub_model = KNeighborsClassifier(**self.classifier_info_)

                elif classifier == 'logistic':
                    voting_sub_model = LogisticRegression(**self.classifier_info_)

                elif classifier == 'rf':
                    voting_sub_model = ensemble.RandomForestClassifier(**self.classifier_info_)

                elif classifier == 'ex-rf':
                    voting_sub_model = ensemble.ExtraTreesClassifier(**self.classifier_info_)

                elif classifier == 'dt':
                    voting_sub_model = tree.DecisionTreeClassifier(**self.classifier_info_)

                elif classifier == 'ex-dt':
                    voting_sub_model = tree.ExtraTreeClassifier(**self.classifier_info_)

                elif classifier == 'ab-dt':

                    voting_sub_model = ensemble.AdaBoostClassifier(base_estimator=tree.DecisionTreeClassifier(**self.classifier_info_),
                                                                   **self.classifier_info_base)

                elif classifier == 'ab-rf':

                    voting_sub_model = ensemble.AdaBoostClassifier(base_estimator=ensemble.RandomForestClassifier(**self.classifier_info_),
                                                                   **self.classifier_info_base)

                elif classifier == 'ab-ex-rf':

                    voting_sub_model = ensemble.AdaBoostClassifier(base_estimator=ensemble.ExtraTreesClassifier(**self.classifier_info_),
                                                                   **self.classifier_info_base)

                elif classifier == 'ab-ex-dt':

                    voting_sub_model = ensemble.AdaBoostClassifier(base_estimator=tree.ExtraTreeClassifier(**self.classifier_info_),
                                                                   **self.classifier_info_base)

                elif classifier == 'bag-dt':

                    voting_sub_model = ensemble.BaggingClassifier(base_estimator=tree.DecisionTreeClassifier(**self.classifier_info_),
                                                                  **self.classifier_info_base)

                elif classifier == 'bag-ex-dt':

                    voting_sub_model = ensemble.BaggingClassifier(base_estimator=tree.ExtraTreeClassifier(**self.classifier_info_),
                                                                  **self.classifier_info_base)

                elif classifier == 'blag':

                    if not IMBLEARN_INSTALLED:

                        logger.error("""\

                        Imbalanced learn must be installed to use the model. Install from
                        
                        pip install imbalanced-learn

                        """)

                    voting_sub_model = imblearn.BalancedBaggingClassifier(**self.classifier_info_base)

                elif classifier == 'blaf':

                    if not IMBLEARN_INSTALLED:

                        logger.error("""\

                        Imbalanced learn must be installed to use the model. Install from

                        pip install imbalanced-learn

                        """)

                    voting_sub_model = imblearn.BalancedRandomForestClassifier(**self.classifier_info_base)

                elif classifier == 'blab':

                    if not IMBLEARN_INSTALLED:

                        logger.error("""\

                        Imbalanced learn must be installed to use the model. Install from

                        pip install imbalanced-learn

                        """)

                    voting_sub_model = imblearn.RUSBoostClassifier(**self.classifier_info_base)

                elif classifier == 'tpot':

                    if not TPOT_INSTALLED:

                        logger.error("""\

                        Tpot must be installed to use the model.

                        """)

                    voting_sub_model = TPOTClassifier(generations=5, population_size=50, cv=5, verbosity=0)

                elif classifier == 'mondrian':

                    if not SKGARDEN_INSTALLED:

                        logger.error("""\

                        Scikit-garden must be installed to use the Mondrian model.

                        """)

                    voting_sub_model = skgarden.MondrianForestClassifier(**self.classifier_info_)

                elif classifier == 'gb':
                    voting_sub_model = ensemble.GradientBoostingClassifier(**self.classifier_info_)

                elif classifier == 'qda':
                    voting_sub_model = QDA(**self.classifier_info_)

                elif classifier == 'gaussian':
                    voting_sub_model = GaussianProcessClassifier(**self.classifier_info_)

                elif classifier == 'svmc':
                    voting_sub_model = svm.SVC(**self.classifier_info_)

                elif classifier == 'svmnu':
                    voting_sub_model = svm.NuSVC(**self.classifier_info_)

                elif classifier == 'catboost':

                    if not CATBOOST_INSTALLED:

                        logger.error("""\

                        Catboost must be installed to use the model.
                                                
                        """)

                    voting_sub_model = CatBoostClassifier(**self.classifier_info_)

                elif classifier == 'lightgbm':

                    if not LIGHTGBM_INSTALLED:

                        logger.error("""\

                        LightGBM must be installed to use the model.
                        
                        # Anaconda
                        conda install -c conda-forge lightgbm or
                        
                        # Python 2.x
                        # cluster: module load cmake
                        pip install --no-cache-dir --no-binary :all: lightgbm
                        
                        # Python 3.x
                        pip install lightgbm

                        """)

                    voting_sub_model = gbm.LGBMClassifier(**self.classifier_info_)

                elif classifier == 'xgboost':

                    if not XGBOOST_INSTALLED:

                        logger.error("""\

                        XGBoost must be installed to use the model.

                        """)

                    voting_sub_model = XGBClassifier(**self.classifier_info_)

                else:

                    logger.warning('  The model, {MODEL}, is not supported'.format(MODEL=classifier))
                    continue

                # Check if the model supports sample weights.
                try:
                    argi = inspect.getargspec(voting_sub_model.fit)
                except:
                    argi = inspect.getfullargspec(voting_sub_model.fit)

                supports_weights = True if 'sample_weight' in argi.args else False

                logger.info('  Fitting a {MODEL} model ...'.format(MODEL=classifier))

                if supports_weights:

                    voting_sub_model.fit(self.p_vars,
                                         self.labels,
                                         sample_weight=self.sample_weight)

                else:

                    voting_sub_model.fit(self.p_vars,
                                         self.labels)

                if self.calibrate_proba:

                    if self.n_samps >= 1000:

                        cal_model = calibration.CalibratedClassifierCV(base_estimator=voting_sub_model,
                                                                       method='isotonic',
                                                                       cv='prefit')

                    else:

                        cal_model = calibration.CalibratedClassifierCV(base_estimator=voting_sub_model,
                                                                       method='sigmoid',
                                                                       cv='prefit')

                    # # Limit the test size.
                    # samp_thresh = 100000
                    # if self.p_vars_test.shape[0] > samp_thresh:
                    #
                    #     pdf = pd.DataFrame(self.p_vars_test)
                    #     pdf['GROUP'] = self.labels_test
                    #
                    #     n_groups = len(pdf.GROUP.unique())
                    #
                    #     group_samps = int(float(samp_thresh) / n_groups)
                    #
                    #     dfg = pdf.groupby('GROUP', group_keys=False).apply(lambda xr_: xr_.sample(min(len(xr_),
                    #                                                                                   group_samps)))
                    #
                    #     idx = dfg.index.values.ravel()
                    #
                    #     p_vars_test_cal = self.p_vars_test[idx]
                    #     labels_test_cal = self.labels_test[idx]
                    #
                    # else:
                    #
                    #     p_vars_test_cal = self.p_vars_test
                    #     labels_test_cal = self.labels_test

                    logger.info('  Calibrating a {MODEL} model ...'.format(MODEL=classifier))

                    # Calibrate the model on the test data.
                    if isinstance(self.calibrate_test, np.ndarray):

                        assert self.calibrate_test.shape[0] == len(self.calibrate_labels) == len(self.calibrate_weights)

                        cal_model.fit(self.calibrate_test,
                                      self.calibrate_labels,
                                      sample_weight=self.calibrate_weights)

                    else:

                        cal_model.fit(self.p_vars_test,
                                      self.labels_test,
                                      sample_weight=self.sample_weight_test)

                    if isinstance(self.view_calibration, int):

                        from sklearn.calibration import calibration_curve

                        # Plot the calibrated probabilities.

                        cal_prob_pos = cal_model.predict_proba(self.p_vars_test)[:, self.view_calibration-1]
                        uncal_prob_pos = voting_sub_model.predict_proba(self.p_vars_test)[:, self.view_calibration-1]

                        cal_fraction_of_positives, cal_mean_predicted_value = calibration_curve(self.labels_test,
                                                                                                cal_prob_pos,
                                                                                                n_bins=10)

                        uncal_fraction_of_positives, uncal_mean_predicted_value = calibration_curve(self.labels_test,
                                                                                                    uncal_prob_pos,
                                                                                                    n_bins=10)

                        ax = plt.figure().add_subplot(111)

                        ax.plot(cal_mean_predicted_value,
                                cal_fraction_of_positives,
                                's-',
                                c='#5F2871',
                                label='{}, label {:d}, calibrated'.format(classifier, self.view_calibration))

                        ax.plot(uncal_mean_predicted_value,
                                uncal_fraction_of_positives,
                                's-',
                                c='#338A2E',
                                label='{}, label {:d}, Uncalibrated'.format(classifier, self.view_calibration))

                        ax.set_ylabel('Fraction positive')
                        ax.set_xlabel('Mean predicted value')
                        plt.tight_layout(pad=0.1)
                        plt.legend()

                        out_fig = os.path.join(self.fig_location,
                                               '{}_{:d}_calibration.png'.format(classifier,
                                                                                self.view_calibration))

                        logger.info('  Calibration curves saved to {}'.format(out_fig))

                        plt.savefig(out_fig, dpi=300)

                        sys.exit()

                    # Update the voting list.
                    classifier_list.append((classifier,
                                            copy(cal_model)))

                else:

                    # Update the voting list.
                    classifier_list.append((classifier,
                                            copy(voting_sub_model)))

                ci += 1

            vote_weights = None if 'vote_weights' not in classifier_info else classifier_info['vote_weights']

            # self.model = ensemble.VotingClassifier(estimators=classifier_list,
            #                                        voting='soft',
            #                                        weights=vote_weights)

            self.model = VotingClassifier(estimators=classifier_list,
                                          weights=vote_weights,
                                          y=self.labels)

            # Reset the original classifier info.
            self.classifier_info = copy(classifier_info)

        else:

            if self.classifier_info['classifier'] in ['ABR', 'gbr', 'ex-rfr', 'rfr', 'ex-rfr', 'SVR', 'SVRA']:
                self.discrete = False
            else:
                self.discrete = True

            if self.classifier_info['classifier'] == 'bayes':

                self.model = GaussianNB()

                # self.model = cv2.ml.NormalBayesClassifier_create()

            elif self.classifier_info['classifier'] == 'CART':
                self.model = cv2.ml.DTrees_create()

            elif self.classifier_info['classifier'] in ['cvrf', 'CVRFR']:

                if not self.get_probs:
                    self.model = cv2.ml.RTrees_create()

            # elif self.classifier_info['classifier'] == 'cvmlp':
            #
            #     if self.input_model:
            #     self.model = cv2.ml.ANN_MLP_create()
            #     # else:
            #     #     self.model = cv2.ml.ANN_MLP_create(np.array([self.n_feas, self.classifier_info['n_hidden'],
            #     #                                                  self.n_classes]))

            elif self.classifier_info['classifier'] in ['cvsvm', 'cvsvma', 'CVSVMR', 'CVSVMRA']:
                self.model = cv2.ml.SVM_create()

            elif self.classifier_info['classifier'] == 'dt':
                self.model = tree.DecisionTreeClassifier(**self.classifier_info_)

            elif self.classifier_info['classifier'] == 'dtr':
                self.model = tree.DecisionTreeRegressor(**self.classifier_info_)

            elif self.classifier_info['classifier'] == 'ex-dt':
                self.model = tree.ExtraTreeClassifier(**self.classifier_info_)

            elif self.classifier_info['classifier'] == 'ex-dtr':
                self.model = tree.ExtraTreeRegressor(**self.classifier_info_)

            elif self.classifier_info['classifier'] == 'logistic':
                self.model = LogisticRegression(**self.classifier_info_)

            elif self.classifier_info['classifier'] == 'nn':
                self.model = KNeighborsClassifier(**self.classifier_info_)

            elif self.classifier_info['classifier'] == 'rf':
                self.model = ensemble.RandomForestClassifier(**self.classifier_info_)

            elif self.classifier_info['classifier'] == 'ex-rf':
                self.model = ensemble.ExtraTreesClassifier(**self.classifier_info_)

            elif self.classifier_info['classifier'] == 'rfr':
                self.model = ensemble.RandomForestRegressor(**self.classifier_info_)

            elif self.classifier_info['classifier'] == 'ex-rfr':
                self.model = ensemble.ExtraTreesRegressor(**self.classifier_info_)

            elif self.classifier_info['classifier'] == 'ab-dt':

                self.model = ensemble.AdaBoostClassifier(base_estimator=tree.DecisionTreeClassifier(**self.classifier_info_),
                                                         **self.classifier_info_base)

            elif self.classifier_info['classifier'] == 'ab-rf':

                self.model = ensemble.AdaBoostClassifier(base_estimator=ensemble.RandomForestClassifier(**self.classifier_info_),
                                                         **self.classifier_info_base)

            elif self.classifier_info['classifier'] == 'ab-ex-rf':

                self.model = ensemble.AdaBoostClassifier(base_estimator=ensemble.ExtraTreesClassifier(**self.classifier_info_),
                                                         **self.classifier_info_base)

            elif self.classifier_info['classifier'] == 'ab-ex-dt':

                self.model = ensemble.AdaBoostClassifier(base_estimator=tree.ExtraTreeClassifier(**self.classifier_info_),
                                                         **self.classifier_info_base)

            elif self.classifier_info['classifier'] == 'abr':

                self.model = ensemble.AdaBoostRegressor(base_estimator=tree.DecisionTreeRegressor(**self.classifier_info_),
                                                        **self.classifier_info_base)

            elif self.classifier_info['classifier'] == 'abr-ex-dtr':

                self.model = ensemble.AdaBoostRegressor(base_estimator=tree.ExtraTreeRegressor(**self.classifier_info_),
                                                        **self.classifier_info_base)

            elif self.classifier_info['classifier'] == 'bag-dt':

                self.model = ensemble.BaggingClassifier(base_estimator=tree.DecisionTreeClassifier(**self.classifier_info_),
                                                        **self.classifier_info_base)

            elif self.classifier_info['classifier'] == 'bag-dtr':

                self.model = ensemble.BaggingRegressor(base_estimator=tree.DecisionTreeRegressor(**self.classifier_info_),
                                                       **self.classifier_info_base)

            elif self.classifier_info['classifier'] == 'bag-ex-dt':

                self.model = ensemble.BaggingClassifier(base_estimator=tree.ExtraTreeClassifier(**self.classifier_info_),
                                                        **self.classifier_info_base)

            elif self.classifier_info['classifier'] == 'blag':

                if not IMBLEARN_INSTALLED:

                    logger.error("""\

                    Imbalanced learn must be installed to use the model. Install from

                    pip install imbalanced-learn

                    """)

                self.model = imblearn.BalancedBaggingClassifier(**self.classifier_info_base)

            elif self.classifier_info['classifier'] == 'blaf':

                if not IMBLEARN_INSTALLED:

                    logger.error("""\

                    Imbalanced learn must be installed to use the model. Install from

                    pip install imbalanced-learn

                    """)

                self.model = imblearn.BalancedRandomForestClassifier(**self.classifier_info_base)

            elif self.classifier_info['classifier'] == 'blab':

                if not IMBLEARN_INSTALLED:

                    logger.error("""\

                    Imbalanced learn must be installed to use the model. Install from

                    pip install imbalanced-learn

                    """)

                self.model = imblearn.RUSBoostClassifier(**self.classifier_info_base)

            elif self.classifier_info['classifier'] == 'tpot':

                if not TPOT_INSTALLED:

                    logger.error("""\

                    Tpot must be installed to use the model.

                    """)

                self.model = TPOTClassifier(generations=5, population_size=50, cv=5, verbosity=0)

            elif self.classifier_info['classifier'] == 'mondrian':

                if not SKGARDEN_INSTALLED:

                    logger.error("""\

                    Scikit-garden must be installed to use the Mondrian model.

                    """)

                self.model = skgarden.MondrianForestClassifier(**self.classifier_info_)

            elif self.classifier_info['classifier'] == 'gb':
                self.model = ensemble.GradientBoostingClassifier(**self.classifier_info_)

            elif self.classifier_info['classifier'] == 'gbr':
                self.model = ensemble.GradientBoostingRegressor(**self.classifier_info_)

            elif self.classifier_info['classifier'] == 'svmc':
                self.model = svm.SVC(**self.classifier_info_)

            elif self.classifier_info['classifier'] == 'svmnu':
                self.model = svm.NuSVC(**self.classifier_info_)

            elif self.classifier_info['classifier'] == 'qda':
                self.model = QDA(**self.classifier_info_)

            elif self.classifier_info['classifier'] == 'gaussian':
                self.model = GaussianProcessClassifier(**self.classifier_info_)

            elif self.classifier_info['classifier'] == 'catboost':

                if not CATBOOST_INSTALLED:

                    logger.error("""\

                    Catboost must be installed to use the model.

                    """)

                self.model = CatBoostClassifier(**self.classifier_info_)

            elif self.classifier_info['classifier'] == 'lightgbm':

                if not LIGHTGBM_INSTALLED:

                    logger.error("""\

                    LightGBM must be installed to use the model. 
                    
                    # Anaconda
                    conda install -c conda-forge lightgbm or

                    # Python 2.x
                    # cluster: module load cmake
                    pip install --no-cache-dir --no-binary :all: lightgbm

                    # Python 3.x
                    pip install lightgbm

                    """)

                self.model = gbm.LGBMClassifier(**self.classifier_info_)

            elif self.classifier_info['classifier'] == 'xgboost':

                if not XGBOOST_INSTALLED:

                    logger.error("""\

                    XGBoost must be installed to use the model.

                    """)

                self.model = XGBClassifier(**self.classifier_info_)

            elif self.classifier_info['classifier'] == 'chaincrf':

                if self.classifier_info_['n_jobs'] == 1:

                    self.model = ssvm.FrankWolfeSSVM(ChainCRF(directed=True),
                                                     **self.classifier_info_)

                else:

                    self.model = ssvm.OneSlackSSVM(ChainCRF(directed=True),
                                                   **self.classifier_info_)

            elif self.classifier_info['classifier'] == 'gridcrf':

                try:

                    # CURRENTLY EXPERIMENTAL AND DOES NOT
                    #   SUPPORT PARALLEL PROCESSING
                    # if self.classifier_info_['n_jobs'] == 1:
                    #
                    #     self.model = ssvm.FrankWolfeSSVM(GridCRF(inference_method='qpbo',
                    #                                              neighborhood=4),
                    #                                      **self.classifier_info_)
                    #
                    # else:

                    self.model = ssvm.OneSlackSSVM(GridCRF(**self.grid_info),
                                                   **self.classifier_info_)

                except:

                    logger.error('  The Grid CRF failed.')
                    raise RuntimeError

            elif self.classifier_info['classifier'] == 'ORRF':

                # try:
                #     import otbApplication as otb
                # except ImportError:
                #     raise ImportError('Orfeo tooblox needs to be installed')

                v_info = vector_tools.vopen(self.in_shapefile)

                if v_info.shp_geom_name.lower() == 'point':
                    sys.exit('\nThe input shapefile must be a polygon.\n')

                if os.path.isfile(self.out_stats):
                    logger.info('  The statistics already exist')
                else:

                    if self.stats_from_image:

                        # image statistics
                        com = 'otbcli_ComputeImagesStatistics -il %s -out %s' % (self.input_image, self.out_stats)

                        subprocess.call(com, shell=True)

                    else:

                        gap_1 = '    '
                        gap_2 = '        '

                        xml_string = '<?xml version="1.0" ?>\n<FeatureStatistics>\n{}<Statistic name="mean">\n{}'.format(gap_1, gap_2)

                        # gather stats from samples
                        for fea_pos in range(0, self.n_feas):

                            stat_line = '<StatisticVector value="%f" />' % self.p_vars[:, fea_pos].mean()

                            # add the line to the xml string
                            if (fea_pos + 1) == self.n_feas:
                                xml_string = '%s%s\n%s' % (xml_string, stat_line, gap_1)
                            else:
                                xml_string = '%s%s\n%s' % (xml_string, stat_line, gap_2)

                        xml_string = '%s</Statistic>\n%s<Statistic name="stddev">\n%s' % (xml_string, gap_1, gap_2)

                        # gather stats from samples
                        for fea_pos in range(0, self.n_feas):

                            stat_line = '<StatisticVector value="%f" />' % self.p_vars[:, fea_pos].std()

                            # add the line to the xml string
                            if (fea_pos + 1) == self.n_feas:
                                xml_string = '%s%s\n%s' % (xml_string, stat_line, gap_1)
                            else:
                                xml_string = '%s%s\n%s' % (xml_string, stat_line, gap_2)

                        xml_string = '%s</Statistic>\n</FeatureStatistics>\n' % xml_string

                        with open(self.out_stats, 'w') as xml_wr:
                            xml_wr.writelines(xml_string)

                # app = otb.Registry.CreateApplication('ComputeImagesStatistics')
                # app.SetParameterString('il', input_image)
                # app.SetParameterString('out', output_stats)
                # app.ExecuteAndWriteOutput()

                if os.path.isfile(self.output_model):
                    os.remove(self.output_model)

                # train the model
                com = 'otbcli_TrainImagesClassifier -io.il {} -io.vd {} -io.imstat {} -classifier rf \
                -classifier.rf.max {:d} -classifier.rf.nbtrees {:d} \
                -classifier.rf.min {:d} -classifier.rf.var {:d} -io.out {}'.format(self.input_image,
                                                                                   self.in_shapefile,
                                                                                   self.out_stats,
                                                                                   self.classifier_info['max_depth'],
                                                                                   self.classifier_info['trees'],
                                                                                   self.classifier_info['min_samps'],
                                                                                   self.classifier_info['rand_vars'],
                                                                                   self.output_model)

                subprocess.call(com, shell=True)

                # app = otb.Registry.CreateApplication('TrainImagesClassifier')
                # app.SetParameterString('io.il', input_image)
                # app.SetParameterString('io.vd', input_shapefile)
                # app.SetParameterString('io.imstat', output_stats)
                # app.SetParameterString('classifier', 'rf')
                # app.SetParameterString('classifier.rf.max', str(classifier_info['max_depth']))
                # app.SetParameterString('classifier.rf.nbtrees', str(classifier_info['trees']))
                # app.SetParameterString('classifier.rf.min', str(classifier_info['min_samps']))
                # app.SetParameterString('classifier.rf.var', str(classifier_info['rand_vars']))
                # app.SetParameterString('io.out', output_model)
                # app.ExecuteAndWriteOutput()

            else:

                logger.error('  The model {} is not supported'.format(self.classifier_info['classifier']))
                raise NameError

    def _set_parameters(self):

        """Sets model parameters for OpenCV"""

        #############################################
        # Set algorithm parameters for OpenCV models.
        #############################################

        if self.classifier_info['classifier'] in ['CART', 'cvrf', 'CVEX_RF']:

            self.model.setMaxDepth(self.classifier_info['max_depth'])
            self.model.setMinSampleCount(self.classifier_info['min_samps'])
            self.model.setCalculateVarImportance(self.classifier_info['calc_var_importance'])
            self.model.setActiveVarCount(self.classifier_info['rand_vars'])
            self.model.setTermCriteria(self.classifier_info['term_crit'])

            if self.classifier_info['priors'].min() < 1:
                self.model.setPriors(self.classifier_info['priors'])
            
            self.model.setTruncatePrunedTree(self.classifier_info['truncate'])

        elif self.classifier_info['classifier'] == 'cvmlp':

            n_steps = 1000
            max_err = .0001
            step_size = .3
            momentum = .2

            # cv2.TERM_CRITERIA_EPS
            self.parameters = dict(term_crit=(cv2.TERM_CRITERIA_COUNT, n_steps, max_err),
                                   train_method=cv2.ANN_MLP_TRAIN_PARAMS_BACKPROP,
                                   bp_dw_scale=step_size,
                                   bp_moment_scale=momentum)

        elif self.classifier_info['classifier'] == 'cvsvm':

            self.model.setC(self.classifier_info_svm['C'])
            self.model.setGamma(self.classifier_info_svm['gamma'])
            self.model.setKernel(cv2.ml.SVM_RBF)
            self.model.setType(cv2.ml.SVM_C_SVC)

            # self.parameters = dict(kernel_type=cv2.ml.SVM_RBF,
            #                        svm_type=cv2.ml.SVM_C_SVC,
            #                        C=self.classifier_info_svm['C'],
            #                        gamma=self.classifier_info_svm['gamma'])

        elif self.classifier_info['classifier'] == 'cvsvma':

            # SVM, parameters optimized
            self.parameters = dict(kernel_type=cv2.ml.SVM_RBF,
                                   svm_type=cv2.ml.SVM_C_SVC)

        elif self.classifier_info['classifier'] == 'CVSVMR':

            # SVM regression
            self.parameters = dict(kernel_type=cv2.ml.SVM_RBF,
                                   svm_type=cv2.ml.SVM_NU_SVR,
                                   C=self.classifier_info_svm['C'],
                                   gamma=self.classifier_info_svm['gamma'],
                                   nu=self.classifier_info_svm['nu'],
                                   p=self.classifier_info_svm['p'])

        elif self.classifier_info['classifier'] == 'CVSVMRA':

            # SVM regression, parameters optimized
            self.parameters = dict(kernel_type=cv2.ml.SVM_RBF,
                                   svm_type=cv2.ml.SVM_NU_SVR,
                                   nu=self.classifier_info['nu'])

        else:

            self.parameters = None

    def _train_model(self):

        """
        Trains a model and saves to file if prompted
        """

        if not self.be_quiet:

            if hasattr(self.model, 'is_prefit_model'):
                logger.info('  The model has already been trained as a voting model.')
            else:

                if not hasattr(self, 'n_samps'):
                    self.n_samps = self.p_vars.shape[0]

                if not hasattr(self, 'n_feas'):
                    self.n_feas = self.p_vars.shape[1]

                if self.classifier_info['classifier'][0].lower() in 'aeiou':
                    a_or_an = 'an'
                else:
                    a_or_an = 'a'

                if isinstance(self.classifier_info['classifier'], list):

                    logger.info('  Training a voting model with {} ...'.format(','.join(self.classifier_info['classifier'])))

                else:

                    logger.info('  Training {} {} model with {:,d} samples and {:,d} variables ...'.format(a_or_an,
                                                                                                           self.classifier_info['classifier'],
                                                                                                           self.n_samps,
                                                                                                           self.n_feas))

        # OpenCV tree-based models
        if self.classifier_info['classifier'] in ['CART', 'cvrf', 'CVEX_RF']:

            self.model.train(self.p_vars, 0, self.labels)
            # self.model.train(self.p_vars, cv2.CV_ROW_SAMPLE, self.labels, params=self.parameters)

        # OpenCV tree-based regression
        elif self.classifier_info['classifier'] in ['CVRFR', 'CVEX_RFR']:

            self.model.train(self.p_vars, cv2.CV_ROW_SAMPLE, self.labels,
                             varType=np.zeros(self.n_feas+1, dtype='uint8'), params=self.parameters)

        elif self.classifier_info['classifier'] == 'cvmlp':

            # Convert input strings to binary zeros and ones, and set the output
            # array to all -1's with ones along the diagonal.
            targets = -1 * np.ones((self.n_samps, self.n_classes), 'float')

            for i in range(0, self.n_samps):

                lab_idx = sorted(self.classes).index(self.labels[i])

                targets[i, lab_idx] = 1

            self.model.train(self.p_vars, targets, None, params=self.parameters)

        elif self.classifier_info['classifier'] in ['cvsvm', 'CVSVMR']:

            if isinstance(self.rank_method, str):
                self.rank_feas(rank_method=self.rank_method, top_feas=self.top_feas)
                # self.model.train(self.p_vars, self.labels, varIdx=self.ranked_feas-1, params=self.parameters)
                self.model.train(self.p_vars, self.labels, varIdx=self.ranked_feas-1)
            else:
                # self.model.train(self.p_vars, self.labels, params=self.parameters)
                self.model.train(self.p_vars, 0, self.labels)

        elif self.classifier_info['classifier'] in ['cvsvma', 'cvsvra']:

            logger.info('  Be patient. Auto tuning can take a while.')

            self.model.train_auto(self.p_vars, self.labels, None, None, params=self.parameters, k_fold=10)

        elif self.classifier_info['classifier'] in ['chaincrf', 'gridcrf']:

            if self.classifier_info['classifier'] == 'chaincrf':

                self.p_vars, self.labels, self.p_vars_test = self._transform4crf(p_vars2reshape=self.p_vars,
                                                                                 labels2reshape=self.labels,
                                                                                 p_vars_test2reshape=self.p_vars_test)

            self.model.fit(self.p_vars, self.labels)

        # Scikit-learn models
        else:

            if not hasattr(self.model, 'is_prefit_model'):

                # Check if the model supports sample weights.
                try:
                    argi = inspect.getargspec(self.model.fit)
                except:
                    argi = inspect.getfullargspec(self.model.fit)

                if 'sample_weight' in argi.args:

                    self.model.fit(self.p_vars,
                                   self.labels,
                                   sample_weight=self.sample_weight)

                else:

                    self.model.fit(self.p_vars,
                                   self.labels)

                if self.calibrate_proba:

                    if self.n_samps >= 1000:

                        self.model = calibration.CalibratedClassifierCV(base_estimator=copy(self.model),
                                                                        method='isotonic',
                                                                        cv='prefit')

                    else:

                        self.model = calibration.CalibratedClassifierCV(base_estimator=copy(self.model),
                                                                        method='sigmoid',
                                                                        cv='prefit')

                    # # Limit the test size.
                    # samp_thresh = 100000
                    # if self.p_vars_test.shape[0] > samp_thresh:
                    #
                    #     pdf = pd.DataFrame(self.p_vars_test)
                    #     pdf['GROUP'] = self.labels_test
                    #
                    #     n_groups = len(pdf.GROUP.unique())
                    #
                    #     group_samps = int(float(samp_thresh) / n_groups)
                    #
                    #     dfg = pdf.groupby('GROUP', group_keys=False).apply(lambda xr_: xr_.sample(min(len(xr_),
                    #                                                                                   group_samps)))
                    #
                    #     idx = dfg.index.values.ravel()
                    #
                    #     p_vars_test_cal = self.p_vars_test[idx]
                    #     labels_test_cal = self.labels_test[idx]
                    #
                    # else:
                    #
                    #     p_vars_test_cal = self.p_vars_test
                    #     labels_test_cal = self.labels_test

                    logger.info('  Calibrating a {MODEL} model ...'.format(MODEL=self.classifier_info['classifier']))

                    # Calibrate the model on the test data.
                    if isinstance(self.calibrate_test, np.ndarray):

                        assert self.calibrate_test.shape[0] == len(self.calibrate_labels) == len(self.calibrate_weights)

                        self.model.fit(self.calibrate_test,
                                       self.calibrate_labels,
                                       sample_weight=self.calibrate_weights)

                    else:

                        self.model.fit(self.p_vars_test,
                                       self.labels_test,
                                       sample_weight=self.sample_weight_test)

                    feature_importances_ = None

                    # Keep the feature importances.
                    if hasattr(self.model, 'feature_importances_'):
                        feature_importances_ = copy(self.model.feature_importances_)

                    if isinstance(feature_importances_, np.ndarray):
                        self.model.feature_importances_ = feature_importances_

                    self.calibrated = True

                    # if hasattr(self.model, 'estimators'):
                    #     self.model.classes_ = self.model.estimators[0][1].classes_

        if isinstance(self.output_model, str):

            logger.info('  Saving model to file ...')

            compress = ('zlib', 5) if self.compress_model else 0

            if 'CV' in self.classifier_info['classifier']:

                try:

                    self.model.save(self.output_model)

                    # Dump the parameters to a text file.
                    joblib.dump([self.classifier_info,
                                 self.model,
                                 self.sample_info_dict],
                                self.output_model,
                                compress=compress,
                                protocol=-1)

                except:

                    logger.error('  Could not save {} to file.'.format(self.output_model))
                    raise IOError

            else:

                try:

                    joblib.dump([self.classifier_info,
                                 self.model,
                                 self.sample_info_dict],
                                self.output_model,
                                compress=compress,
                                protocol=-1)

                except:

                    logger.error('  Could not save {} to file.'.format(self.output_model))
                    raise IOError

            # Get test accuracy, if possible.
            if hasattr(self, 'p_vars_test'):

                if isinstance(self.p_vars_test, np.ndarray):

                    # try:

                    self.test_accuracy(out_acc=self.out_acc,
                                       discrete=self.discrete)

                    # except:
                    #     logger.warning('  Could not perform model validation.')

    def _transform4crf(self,
                       p_vars2reshape=None,
                       labels2reshape=None,
                       p_vars_test2reshape=None):

        """
        Transforms variables and labels for linear-chain Conditional Random Fields

        Args:
            p_vars2reshape (Optional[2d array])
            labels2reshape (Optional[1d array like])
            p_vars_test2reshape (Optional[2d array])
        """

        p_vars_r = None
        labels_r = None
        p_vars_test_r = None
        constant = np.array([1.0], dtype='float64').reshape(1, 1)

        if isinstance(p_vars2reshape, np.ndarray):

            if hasattr(self, 'n_feas'):

                if isinstance(self.n_feas, int):
                    reshape_features = self.n_feas
                else:
                    reshape_features = p_vars2reshape.shape[1]

            else:
                reshape_features = p_vars2reshape.shape[1]

            p_vars_r = np.array([np.hstack((pv_.reshape(1, reshape_features), constant))
                                 for pv_ in p_vars2reshape], dtype='float64')

        if isinstance(labels2reshape, np.ndarray):
            labels_r = np.array([np.array([label_], dtype='int64') for label_ in labels2reshape], dtype='int64')

        if isinstance(p_vars_test2reshape, np.ndarray):

            if hasattr(self, 'n_feas'):

                if isinstance(self.n_feas, int):
                    reshape_features = self.n_feas
                else:
                    reshape_features = p_vars_test2reshape.shape[1]

            else:
                reshape_features = p_vars_test2reshape.shape[1]

            p_vars_test_r = np.array([np.hstack((pv_.reshape(1, reshape_features), constant))
                                      for pv_ in p_vars_test2reshape], dtype='float64')

        return p_vars_r, labels_r, p_vars_test_r

    def predict_array(self,
                      array2predict,
                      rows,
                      cols,
                      relax_probabilities=False,
                      plr_window_size=5,
                      plr_matrix=None,
                      plr_iterations=3,
                      morphology=False,
                      do_not_morph=None,
                      d_type='byte'):

        """
        Makes predictions on an array

        Args:
            array2predict (2d array): [samples x predictors]
            rows (int): The array rows for reshaping.
            cols (int): The array columns for reshaping.
            relax_probabilities (Optional[bool]): Whether to relax posterior probabilities. Default is False.
            plr_window_size (Optional[int]): The window size for probabilistic label relaxation. Default is 5.
            plr_matrix (Optional[2d array]): The class compatibility matrix. Default is None.
            plr_iterations (Optional[int]): The probabilistic label relaxation iterations. Default is 3.
            morphology (Optional[bool]): Whether to apply image morphology to the predicted classes.
                Default is False.
            do_not_morph (Optional[int list]): A list of classes not to morph with `morphology=True`. Default is None.
            d_type (Optional[str]): The output image data type. Default is 'byte'.
                Choices are ['byte', 'uint16', 'uint32', 'uint64', 'int16', 'int32', 'int64'].
                *If `morphology=True`, `d_type` is automatically set as 'byte'. For regression models, `d_type` is
                automatically set as 'float32'.

        Returns:
            Predictions as a 2d array
        """

        if self.classifier_info['classifier'] in ['c5', 'cubist']:

            features = ro.r.matrix(array2predict,
                                   nrow=array2predict.shape[0],
                                   ncol=array2predict.shape[1])

            features.colnames = StrVector(self.headers[:-1])

            return _do_c5_cubist_predict(self.model, self.classifier_info['classifier'], features)

        else:

            if relax_probabilities:

                return predict_scikit_probas_static(array2predict,
                                                    self.model,
                                                    rows,
                                                    cols,
                                                    0,
                                                    0,
                                                    rows,
                                                    cols,
                                                    morphology,
                                                    do_not_morph,
                                                    plr_matrix,
                                                    plr_window_size,
                                                    plr_iterations,
                                                    self.d_type)

            else:
                return raster_tools.STORAGE_DICT_NUMPY[d_type](self.model.predict(array2predict).reshape(rows, cols))

    def predict(self,
                input_image,
                output_image,
                additional_layers=None,
                band_check=-1,
                bands2open=None,
                ignore_feas=None,
                in_stats=None,
                in_model=None,
                mask_background=None,
                background_band=1,
                background_value=0,
                minimum_observations=0,
                observation_band=0,
                scale_factor=1.0,
                row_block_size=1000,
                col_block_size=1000,
                n_jobs=-1,
                n_jobs_vars=-1,
                gdal_cache=256,
                overwrite=False,
                track_blocks=False,
                predict_probs=False,
                relax_probabilities=False,
                plr_window_size=5,
                plr_iterations=3,
                plr_matrix=None,
                write2blocks=False,
                block_range=None,
                morphology=False,
                do_not_morph=None,
                d_type='byte',
                **kwargs):

        """
        Applies a model to predict class labels

        Args:
            input_image (str): The input image to classify.
            output_image (str): The output image.
            additional_layers (Optional[list]): A list of additional images (layers) that are not part
                of `input_image`.
            band_check (Optional[int]): The band to check for 'no data'. Default is -1, or do not perform check. 
            bands2open (Optional[list]): A list of bands to open, otherwise opens all bands. Default is None.
            ignore_feas (Optional[list]): A list of features (band layers) to ignore. Default is an empty list,
                or use all features.
            in_stats (Optional[str]): A XML statistics file. Default is None. *Only applicable to Orfeo models.
            in_model (Optional[str]): A model file to load. Default is None. *Only applicable to Orfeo
                and C5/Cubist models.
            mask_background (Optional[str or 2d array]): An image or array to use as a background mask. Default is None.
            background_band (int): The band from `mask_background` to use for null background value. Default is 1.
            background_value (Optional[int]): The background value in `mask_background`. Default is 0.
            minimum_observations (Optional[int]): A minimum number of observations in `mask_background` to be
                recoded to 0. Default is 0, or no minimum observation filter.
            observation_band (Optional[int]): The band position in `mask_background` of the `minimum_observations`
                counts. Default is 0.
            scale_factor (Optional[float]): The scale factor for CRF models. Default is 1.
            row_block_size (Optional[int]): The row block size (pixels). Default is 1024.
            col_block_size (Optional[int]): The column block size (pixels). Default is 1024.
            n_jobs (Optional[int]): The number of processors to use for parallel mapping. Default is -1, or all
                available processors.
            n_jobs_vars (Optional[int]): The number of processors to use for parallel band loading.
                Default is -1, or all available processors.
            gdal_cache (Optional[int]). The GDAL cache (MB). Default is 256.
            overwrite (Optional[bool]): Whether to overwrite an existing `output_image`. Default is False.
            track_blocks (Optional[bool]): Whether to keep a record of processed blocks. Default is False.
            predict_probs (Optional[bool]): Whether to write class probabilities to file in place of hard decisions.
                Default is False.
            relax_probabilities (Optional[bool]): Whether to relax posterior probabilities. Default is False.
            plr_window_size (Optional[int]): The window size for probabilistic label relaxation. Default is 5.
            plr_iterations (Optional[int]): The number of iterations for probabilistic label relaxation. Default is 3.
            plr_matrix (Optional[2d array]): The class compatibility matrix. Default is None.
            write2blocks (Optional[bool]): Whether to write to individual blocks, otherwise write to one image.
                Default is False.
                *In the event of True, each block will be given the name `base image_####base extension`.
            block_range (Optional[list or tuple]): A start and end range for block processing. Default is None,
                or start at the first block.
            morphology (Optional[bool]): Whether to apply image morphology to the predicted classes.
                Default is False.
            do_not_morph (Optional[int list]): A list of classes not to morph with `morphology=True`. Default is None.
            d_type (Optional[str]): The output image data type. Default is 'byte'.
                Choices are ['byte', 'uint16', 'uint32', 'uint64', 'int16', 'int32', 'int64'].
                *If `morphology=True`, `d_type` is automatically set as 'byte'. For regression models, `d_type` is
                automatically set as 'float32'.
            kwargs (Optional): Image read options passed to `mpglue.raster_tools.ropen.read`.
            
        Returns:
            None, writes to `output_image`.

        Examples:
            >>> import mpglue as gl
            >>> cl = gl.classification()
            >>>
            >>> # You can use x, y coordinates, but note that these must be
            >>> #   supplied to ``predict`` also.
            >>> cl.split_samples('/samples.txt', perc_samp_each=.7)
            >>>
            >>> # Random Forest with Scikit-learn
            >>> cl.construct_model(classifier_info={'classifier': 'rf', 'trees': 100, 'max_depth': 25})
            >>>
            >>> # Random Forest with OpenCV
            >>> cl.construct_model(classifier_info={'classifier': 'cvrf', 'trees': 100,
            >>>                    'max_depth': 25, 'truncate': True})
            >>>
            >>> # Apply the classification model to map image class labels.
            >>> cl.predict('/image_feas.tif', '/image_labels.tif', ignore_feas=[1, 6])
            >>>
            >>> # or use Orfeo to predict class labels
            >>> cl.construct_model(classifier_info={'classifier': 'OR_RF', 'trees': 1000,
            >>>                    'max_depth': 25, 'min_samps': 5, 'rand_vars': 10},
            >>>                    input_image='/image.tif', in_shapefile='/shapefile.shp',
            >>>                    out_stats='/stats.xml', output_model='/rf_model.xml')
            >>>
            >>> cl.predict('/image_feas.tif', '/image_labels.tif',
            >>>            in_stats='/stats.xml', in_model='/rf_model.xml')
        """

        self.input_image = input_image
        self.output_image = output_image
        self.additional_layers = additional_layers
        self.ignore_feas = ignore_feas
        self.bands2open = bands2open
        self.band_check = band_check
        self.row_block_size = row_block_size
        self.col_block_size = col_block_size
        self.mask_background = mask_background
        self.background_band = background_band
        self.background_value = background_value
        self.minimum_observations = minimum_observations
        self.observation_band = observation_band
        self.scale_factor = scale_factor
        self.in_model = in_model
        self.gdal_cache = gdal_cache
        self.in_stats = in_stats
        self.n_jobs = n_jobs
        self.n_jobs_vars = n_jobs_vars
        self.chunk_size = (self.row_block_size * self.col_block_size) / 100
        self.overwrite = overwrite
        self.track_blocks = track_blocks
        self.predict_probs = predict_probs
        self.relax_probabilities = relax_probabilities
        self.plr_window_size = plr_window_size
        self.plr_iterations = plr_iterations
        self.plr_matrix = plr_matrix
        self.write2blocks = write2blocks
        self.block_range = block_range
        self.morphology = morphology
        self.do_not_morph = do_not_morph
        self.d_type = d_type
        self.kwargs = kwargs

        if self.n_jobs == -1:
            self.n_jobs = joblib.cpu_count()

        if not hasattr(self, 'classifier_info'):

            logger.warning("""\
            
            There is no `classifier_info` object. Be sure to run `construct_model`
            or `construct_r_model` before running `predict`.
            
            """)

            return

        if not hasattr(self, 'model'):

            logger.warning("""\
            
            There is no trained `model` object. Be sure to run `construct_model`
            or `construct_r_model` before running `predict`.
            
            """)

            return

        self.dir_name, f_name = os.path.split(self.output_image)
        self.output_image_base, self.output_image_ext = os.path.splitext(f_name)

        if not self.dir_name and not os.path.isabs(f_name):
            self.dir_name = os.path.abspath('.')

        # Delete files
        if os.path.isfile(output_image) and self.overwrite and not self.write2blocks:

            os.remove(output_image)

            for ext in ['.ovr', '.aux.xml']:

                if os.path.isfile(os.path.join(self.dir_name, '{}{}'.format(f_name, ext))):
                    os.remove(os.path.join(self.dir_name, '{}{}'.format(f_name, ext)))

        self.out_image_temp = os.path.join(self.dir_name, '{}_temp.tif'.format(self.output_image_base))
        self.temp_model_file = os.path.join(self.dir_name, 'temp_model_file.txt')

        if not os.path.isdir(self.dir_name):
            os.makedirs(self.dir_name)

        if self.write2blocks:

            logger.info('  Predicting class labels from {} and writing to {} blocks ...'.format(self.input_image,
                                                                                                self.output_image))

        else:

            logger.info('  Predicting class labels from {} and writing to {} ...'.format(self.input_image,
                                                                                         self.output_image))

        # Conditional Random Fields
        if self.classifier_info['classifier'] == 'gridcrf':
            self._predict4crf(**self.kwargs)

        # Orfeo Toolbox application
        elif 'OR' in self.classifier_info['classifier']:
            self._predict4orf()

        # Scikit-learn or OpenCV
        else:

            self.open_image = False

            self.i_info = raster_tools.ropen(self.input_image)

            # Block record keeping.
            if self.track_blocks and not self.write2blocks:

                self.record_keeping = os.path.join(self.dir_name, '{}_record.txt'.format(self.output_image_base))

                if os.path.isfile(self.record_keeping):
                    self.record_list = self.load(self.record_keeping)
                else:
                    self.record_list = list()

            # Output image information.
            self.o_info = self.i_info.copy()

            # OUTPUT BANDS
            if self.predict_probs:

                if not hasattr(self.model, 'predict_proba'):

                    logger.warning('  The model must have a `predict_proba` method to prediction class probabilities.')
                    return

                self.o_info.bands = self.n_classes

            else:
                self.o_info.bands = 1

            # OUTPUT DATA TYPE
            if self.predict_probs or (self.classifier_info['classifier'] in ['abr', 'abr-ex-dtr', 'bgr', 'bag-dtr',
                                                                             'rfr', 'ex-rfr', 'svr', 'svra',
                                                                             'cubist', 'dtr']):

                self.o_info.update_info(storage='float32')
                self.d_type = 'float32'

            else:

                if self.morphology:

                    self.o_info.update_info(storage='byte')
                    self.d_type = 'byte'

                else:
                    self.o_info.update_info(storage=self.d_type)

            # Make the predictions
            self._predict()

            if self.open_image:
                self.i_info.close()

            self.o_info.close()

    def _predict4crf(self, **kwargs):

        self.load4crf([self.input_image],
                      None,
                      bands2open=self.bands2open,
                      scale_factor=self.scale_factor,
                      n_jobs=self.n_jobs_vars,
                      **kwargs)

        with raster_tools.ropen(self.input_image) as i_info:

            o_info = i_info.copy()

            # Update the output information.
            o_info.update_info(bands=1,
                               storage='byte')

            if 'j' in kwargs:
                o_info.update_info(left=i_info.left + (kwargs['j'] * i_info.cellY))

            if 'i' in kwargs:
                o_info.update_info(top=i_info.top - (kwargs['i'] * i_info.cellY))

            if 'rows' in kwargs:
                o_info.update_info(rows=kwargs['rows'])

            if 'cols' in kwargs:
                o_info.update_info(cols=kwargs['cols'])

        del i_info

        # Make class predictions and write to file.
        raster_tools.write2raster(np.array(self.model.predict(self.p_vars),
                                           dtype='uint8').reshape(self.im_rows,
                                                                  self.im_cols),
                                  self.output_image,
                                  o_info=o_info)

    def _predict4orf(self):

        # make predictions
        if isinstance(self.in_stats, str):

            if isinstance(self.mask_background, str):

                com = 'otbcli_ImageClassifier -in {} -imstat {} \
                                        -model {} -out {} -ram {:d}'.format(self.input_image,
                                                                            self.in_stats,
                                                                            self.in_model,
                                                                            self.out_image_temp,
                                                                            self.gdal_cache)

            else:
                com = 'otbcli_ImageClassifier -in {} -imstat {} \
                                        -model {} -out {} -ram {:d}'.format(self.input_image,
                                                                            self.in_stats,
                                                                            self.in_model,
                                                                            self.output_image,
                                                                            self.gdal_cache)

        else:

            if isinstance(self.mask_background, str):

                com = 'otbcli_ImageClassifier -in {} -model {} -out {} -ram {:d}'.format(self.input_image,
                                                                                         self.in_model,
                                                                                         self.out_image_temp,
                                                                                         self.gdal_cache)

            else:

                com = 'otbcli_ImageClassifier -in {} -model {} -out {} -ram {:d}'.format(self.input_image,
                                                                                         self.in_model,
                                                                                         self.output_image,
                                                                                         self.gdal_cache)

        try:
            subprocess.call(com, shell=True)
        except:

            logger.warning('  Are you sure the Orfeo Toolbox is installed?')
            return

        if isinstance(self.mask_background, str):

            self._mask_background()

            # app = otb.Registry.CreateApplication('ImageClassifier')
            # app.SetParameterString('in', input_image)
            # app.SetParameterString('imstat', output_stats)
            # app.SetParameterString('model', output_model)
            # app.SetParameterString('out', output_map)
            # app.ExecuteAndWriteOutput()

    def _predict(self):

        # Global variables for parallel processing.
        global features, model_pp, predict_samps, indice_pairs, mdl

        features = None
        model_pp = None
        predict_samps = None
        indice_pairs = None
        mdl = None

        # Load the model.
        if isinstance(self.input_model, str):
            mdl = joblib.load(self.input_model)[1]
        else:
            mdl = self.model

        # Set default indexing variables.
        start_i = 0
        start_j = 0
        rows = self.i_info.rows
        cols = self.i_info.cols
        image_top = self.i_info.top
        image_left = self.i_info.left
        iwo = 0
        jwo = 0

        # Update variables for sub-image predictions.
        start_i, start_j, rows, cols, iwo, jwo = self._set_indexing(start_i,
                                                                    start_j,
                                                                    rows,
                                                                    cols,
                                                                    iwo,
                                                                    jwo)

        # Determine which bands to open.
        self._set_bands2open()

        # Update the output raster size.
        #
        # *This will be overwritten in the
        #   event `write2blocks` is set as True.
        self.o_info.update_info(rows=rows,
                                cols=cols)

        # Setup the object to write to.
        if not self.write2blocks:

            out_raster_object = self._set_output_object()

            if self.predict_probs:

                for cidx in range(1, len(mdl.classes_)+1):

                    out_raster_object.get_band(cidx)
                    out_raster_object.fill(0)

            else:

                out_raster_object.get_band(1)
                out_raster_object.fill(0)

        block_rows, block_cols = raster_tools.block_dimensions(rows,
                                                               cols,
                                                               row_block_size=self.row_block_size,
                                                               col_block_size=self.col_block_size)

        # Determine the number of blocks in the image.
        block_indices, n_blocks = self._set_n_blocks(start_i,
                                                     start_j,
                                                     iwo,
                                                     jwo,
                                                     rows,
                                                     cols,
                                                     block_rows,
                                                     block_cols)

        n_block = 1

        for block_index in block_indices:

            i = block_index[0]
            j = block_index[1]
            n_rows = block_index[2]
            n_cols = block_index[3]
            iw = block_index[4]
            jw = block_index[5]
            rw = block_index[6]
            cw = block_index[7]
            ipadded = block_index[9]
            jpadded = block_index[10]

            logger.info('  Block {:,d} of {:,d} ...'.format(n_block, n_blocks))

            # Setup the object to write to.
            if self.write2blocks:

                if isinstance(self.block_range, list) or isinstance(self.block_range, tuple):

                    if n_block < self.block_range[0]:

                        n_block += 1
                        continue

                    if n_block > self.block_range[1]:
                        break

                self.output_image = os.path.join(self.dir_name,
                                                 '{BASE}_{BLOCK:05d}{EXT}'.format(BASE=self.output_image_base,
                                                                                  BLOCK=n_block,
                                                                                  EXT=self.output_image_ext))

                if os.path.isfile(self.output_image):

                    if self.overwrite:
                        os.remove(self.output_image)
                    else:

                        n_block += 1
                        continue

                # Update the output image
                #   information for the
                #   current block.
                self.o_info.update_info(top=image_top - (i*self.o_info.cellY),
                                        left=image_left + (j*self.o_info.cellY),
                                        rows=n_rows,
                                        cols=n_cols)

                iwo = i
                jwo = j

                out_raster_object = self._set_output_object()

                if not self.predict_probs:

                    out_raster_object.get_band(1)
                    out_raster_object.fill(0)

            n_block += 1

            if self.track_blocks and not self.write2blocks:

                if n_block in self.record_list:

                    logger.info('  Skipping current block ...')
                    continue

            # Check for zeros in the block.
            if self.band_check != -1:

                if self.open_image:

                    self.i_info = raster_tools.ropen(self.input_image)
                    self.open_image = False

                max_check = self.i_info.read(bands2open=self.band_check,
                                             i=i,
                                             j=j,
                                             rows=n_rows,
                                             cols=n_cols).max()

                if max_check == 0:

                    # Close the block file.
                    if self.write2blocks:

                        out_raster_object.close_all()
                        out_raster_object = None

                    continue

            if not self.open_image:

                # Close the image information object because it
                #   needs to be reopened for parallel ``read``.
                self.i_info.close()
                self.open_image = True

            if 'CV' in self.classifier_info['classifier']:

                if len(self.bands2open) != self.model.getVarCount():

                    logger.error('  The number of predictive layers does not match the number of model estimators.')
                    raise AssertionError

            elif (self.classifier_info['classifier'] not in ['c5', 'cubist', 'qda', 'chaincrf']) and \
                    ('CV' not in self.classifier_info['classifier']):

                if hasattr(self.model, 'n_features_'):

                    if len(self.bands2open) != self.model.n_features_:

                        logger.error('  The number of predictive layers does not match the number of model estimators.')
                        raise AssertionError

                if hasattr(self.model, 'base_estimator'):

                    if hasattr(self.model.base_estimator, 'n_features_'):

                        if len(self.bands2open) != self.model.base_estimator.n_features_:

                            logger.error('  The number of predictive layers does not match the number of model estimators.')
                            raise AssertionError

            # Get all the bands for the tile. The shape
            #   of the features is ([rows x columns] x features).
            features = raster_tools.read(image2open=self.input_image,
                                         bands2open=self.bands2open,
                                         i=iw,
                                         j=jw,
                                         rows=rw,
                                         cols=cw,
                                         predictions=True,
                                         d_type='float64',
                                         n_jobs=self.n_jobs_vars)

            n_samples = rw * cw

            if self.use_xy:

                # Create x,y coordinates for the block.
                x_coordinates, y_coordinates = self._create_indices(iw, jw, rw, cw)

                # Append the x,y coordinates to the features.
                features = np.hstack((features,
                                      x_coordinates,
                                      y_coordinates))

            # Reshape the features for CRF models.
            if self.classifier_info['classifier'] == 'chaincrf':
                features = self._transform4crf(p_vars2reshape=features)[0]
            else:

                # Scale the features.
                if self.scaled:
                    features = self.scaler.transform(features)

            if self.func_applier:
                features = self.func_applier(features, self)

            # TODO: add to `func_applier` and remove here
            if self.additional_layers:

                additional_layers = self._get_additional_layers(iw, jw, rw, cw)

                features = np.hstack((features,
                                      additional_layers))

            # Add extra predictive
            #   time series features.
            if self._add_features:

                if not self.ts_indices:

                    if self.use_xy:
                        self.ts_indices = np.array(range(0, features.shape[1]-2), dtype='int64')

                features = self.feature_object.apply_features(X=features,
                                                              ts_indices=self.ts_indices,
                                                              append_features=self.append_features)

            features[np.isnan(features) | np.isinf(features)] = 0.0

            # Get locations of empty features
            null_samples = np.where(features.max(axis=1).reshape(rw, cw) == 0)

            if 'CV' in self.classifier_info['classifier']:

                if self.classifier_info['classifier'] == 'cvmlp':

                    self.model.predict(features, predicted)

                    predicted = np.argmax(predicted, axis=1)

                else:

                    # Setup the global array to write to. This avoids
                    #   passing it to the joblib workers.
                    # predicted = np.empty((n_samples, 1), dtype='uint8')

                    predicted = joblib.Parallel(n_jobs=self.n_jobs,
                                                max_nbytes=None)(joblib.delayed(predict_cv)(chunk,
                                                                                            self.chunk_size,
                                                                                            self.file_name,
                                                                                            self.perc_samp,
                                                                                            self.classes2remove,
                                                                                            self.ignore_feas,
                                                                                            self.use_xy,
                                                                                            self.classifier_info,
                                                                                            self.weight_classes)
                                                                 for chunk in range(0, n_samples, self.chunk_size))

                # transpose and reshape the predicted labels to (rows x columns)
                out_raster_object.write_array(np.array(list(itertools.chain.from_iterable(predicted))).reshape(n_rows,
                                                                                                               n_cols),
                                              j=j-jwo,
                                              i=i-iwo)

            elif self.classifier_info['classifier'] in ['c5', 'cubist']:

                # Load the predictor variables.
                # predict_samps = pandas2ri.py2ri(pd.DataFrame(features))

                predict_samps = ro.r.matrix(features, nrow=n_samples, ncol=len(self.bands2open))
                predict_samps.colnames = StrVector(self.headers[:-1])

                # Get chunks for parallel processing.
                indice_pairs = list()
                for i_ in range(1, n_samples+1, self.chunk_size):

                    n_rows_ = self._num_rows_cols(i_, self.chunk_size, n_samples)
                    indice_pairs.append([i_, n_rows_])

                indice_pairs[-1][1] += 1

                # Make the predictions and convert to a NumPy array.
                if isinstance(self.input_model, str):

                    predicted = joblib.Parallel(n_jobs=self.n_jobs,
                                                max_nbytes=None)(joblib.delayed(predict_c5_cubist)(self.input_model,
                                                                                                   ip)
                                                                 for ip in indice_pairs)

                    # Write the predictions to file.
                    out_raster_object.write_array(np.array(list(itertools.chain.from_iterable(predicted))).reshape(n_rows,
                                                                                                                   n_cols),
                                                  j=j-jwo,
                                                  i=i-iwo)

                else:

                    out_raster_object.write_array(_do_c5_cubist_predict(self.model,
                                                                        self.classifier_info['classifier'],
                                                                        predict_samps).reshape(n_rows,
                                                                                               n_cols),
                                                  j=j-jwo,
                                                  i=i-iwo)

            else:

                # SCIKIT-LEARN MODELS

                if self.predict_probs or self.relax_probabilities:

                    # --------------------------------------
                    # Posterior probability label relaxation
                    # --------------------------------------

                    if self.predict_probs:

                        # Predict class conditional probabilities.
                        predicted = predict_scikit_probas(rw,
                                                          cw,
                                                          ipadded,
                                                          jpadded,
                                                          n_rows,
                                                          n_cols,
                                                          self.morphology,
                                                          self.do_not_morph,
                                                          self.relax_probabilities,
                                                          self.plr_matrix,
                                                          self.plr_window_size,
                                                          self.plr_iterations,
                                                          self.predict_probs,
                                                          self.d_type,
                                                          null_samples)

                        for cidx in range(0, predicted.shape[0]):

                            out_raster_object.write_array(predicted[cidx],
                                                          i=i-iwo,
                                                          j=j-jwo,
                                                          band=cidx+1)

                    else:

                        # Write the predictions to file.
                        out_raster_object.write_array(predict_scikit_probas(rw,
                                                                            cw,
                                                                            ipadded,
                                                                            jpadded,
                                                                            n_rows,
                                                                            n_cols,
                                                                            self.morphology,
                                                                            self.do_not_morph,
                                                                            self.relax_probabilities,
                                                                            self.plr_matrix,
                                                                            self.plr_window_size,
                                                                            self.plr_iterations,
                                                                            self.predict_probs,
                                                                            self.d_type,
                                                                            null_samples),
                                                      j=j-jwo,
                                                      i=i-iwo)

                else:

                    # Get chunks for parallel processing.
                    # indice_pairs = list()
                    #
                    # for i_ in range(0, n_samples, self.chunk_size):
                    #
                    #     n_rows_ = self._num_rows_cols(i_, self.chunk_size, n_samples)
                    #     indice_pairs.append([i_, n_rows_])
                    #
                    # if (self.n_jobs != 0) and (self.n_jobs != 1):
                    #
                    #     # Make the predictions and convert to a NumPy array.
                    #     if isinstance(self.input_model, str):
                    #
                    #         if platform.system() == 'Windows':
                    #
                    #             predicted = joblib.Parallel(n_jobs=self.n_jobs,
                    #                                         max_nbytes=None)(joblib.delayed(predict_scikit_win)(features[ip[0]:ip[0]+ip[1]],
                    #                                                                                             self.input_model)
                    #                                                          for ip in indice_pairs)
                    #
                    #         else:
                    #
                    #             mdl = self.load(self.input_model)[1]
                    #
                    #             pool = multi.Pool(processes=self.n_jobs)
                    #
                    #             predicted = pool.map(predict_scikit, range(0, len(indice_pairs)))
                    #
                    #             pool.close()
                    #             del pool
                    #
                    #     else:
                    #
                    #         mdl = self.model
                    #         predicted = [predict_scikit(ip) for ip in range(0, len(indice_pairs))]
                    #
                    # else:

                    # Make the predictions and convert to a NumPy array.
                    # predicted = [predict_scikit(ip) for ip in range(0, len(indice_pairs))]

                    # Write the predictions to file.
                    # out_raster_object.write_array(np.array(list(itertools.chain.from_iterable(predicted))).reshape(n_rows,
                    #                                                                                                n_cols),
                    #                               j=j-jwo,
                    #                               i=i-iwo)

                    # Write the predictions to file.
                    if self.morphology:

                        if isinstance(self.do_not_morph, list):

                            predictions = np.uint8(mdl.predict(features).reshape(rw, cw))

                            predictions_copy = predictions[ipadded:ipadded+n_rows,
                                                           jpadded:jpadded+n_cols].copy()

                            predictions = pymorph.closerec(pymorph.closerec(predictions,
                                                                            Bdil=pymorph.secross(r=3),
                                                                            Bc=pymorph.secross(r=1)),
                                                           Bdil=pymorph.secross(r=2),
                                                           Bc=pymorph.secross(r=1))[ipadded:ipadded+n_rows,
                                                                                    jpadded:jpadded+n_cols]

                            for do_not_morph_value in self.do_not_morph:
                                predictions[predictions_copy == do_not_morph_value] = do_not_morph_value

                            del predictions_copy

                            out_raster_object.write_array(predictions,
                                                          j=j-jwo,
                                                          i=i-iwo)

                            del predictions

                        else:

                            out_raster_object.write_array(
                                pymorph.closerec(pymorph.closerec(np.uint8(mdl.predict(features).reshape(rw, cw)),
                                                                  Bdil=pymorph.secross(r=3),
                                                                  Bc=pymorph.secross(r=1)),
                                                 Bdil=pymorph.secross(r=2),
                                                 Bc=pymorph.secross(r=1))[ipadded:ipadded+n_rows,
                                                                          jpadded:jpadded+n_cols],
                                j=j-jwo,
                                i=i-iwo)

                    else:

                        np_dtype = raster_tools.STORAGE_DICT_NUMPY[self.d_type]

                        out_raster_object.write_array(np_dtype(mdl.predict(features).reshape(n_rows,
                                                                                             n_cols)),
                                                      j=j-jwo,
                                                      i=i-iwo)

            features = None

            # Close the block file.
            if self.write2blocks:

                out_raster_object.close_all()
                out_raster_object = None

            if self.track_blocks and not self.write2blocks:

                self.record_list.append(n_block)

                if os.path.isfile(self.record_keeping):
                    os.remove(self.record_keeping)

                self.dump(self.record_list,
                          self.record_keeping)

        # Close the file.
        if not self.write2blocks:

            if self.predict_probs:

                for cidx in range(0, len(mdl.classes_)):

                    out_raster_object.get_band(cidx+1)
                    out_raster_object.close_band()

            out_raster_object.close_all()
            out_raster_object = None

        if isinstance(self.mask_background, str) or isinstance(self.mask_background, np.ndarray):
            self._mask_background()

    def _set_indexing(self, start_i, start_j, rows, cols, iwo, jwo):

        if self.kwargs:

            if ('i' in self.kwargs) and ('y' not in self.kwargs):

                start_i = self.kwargs['i']
                self.o_info.update_info(top=self.o_info.top - (start_i*self.o_info.cellY))
                iwo = start_i

            elif ('i' not in self.kwargs) and ('y' in self.kwargs):

                # Index the image by x, y coordinates (in map units).
                self.kwargs['i'] = vector_tools.get_xy_offsets(self.i_info,
                                                               x=999.,
                                                               y=self.kwargs['y'],
                                                               check_position=False)[3]

                start_i = self.kwargs['i']
                self.o_info.update_info(top=self.o_info.top - (start_i*self.o_info.cellY))
                iwo = start_i

            if ('j' in self.kwargs) and ('x' not in self.kwargs):

                start_j = self.kwargs['j']
                self.o_info.update_info(left=self.o_info.left + (start_j*self.o_info.cellY))
                jwo = start_j

            elif ('j' not in self.kwargs) and ('x' in self.kwargs):

                # Index the image by x, y coordinates (in map units).
                self.kwargs['j'] = vector_tools.get_xy_offsets(self.i_info,
                                                               x=self.kwargs['x'],
                                                               y=999.,
                                                               check_position=False)[2]

                start_j = self.kwargs['j']
                self.o_info.update_info(left=self.o_info.left + (start_j*self.o_info.cellY))
                jwo = start_j

            if 'rows' in self.kwargs:

                if self.kwargs['rows'] != -1:
                    rows = self.kwargs['rows']

            if 'cols' in self.kwargs:

                if self.kwargs['cols'] != -1:
                    cols = self.kwargs['cols']

        return start_i, start_j, rows, cols, iwo, jwo

    def _set_bands2open(self):

        """Sets the list of (feature) bands to open"""

        if self.ignore_feas:
            self.bands2open = sorted([bd for bd in range(1, self.i_info.bands+1) if bd not in self.ignore_feas])
        else:

            if not isinstance(self.bands2open, list):
                self.bands2open = list(range(1, self.i_info.bands+1))

    def _set_output_object(self):

        """Creates the raster object to write to"""

        if self.predict_probs:

            return raster_tools.create_raster(self.output_image,
                                              self.o_info,
                                              compress='none',
                                              tile=False,
                                              bigtiff='yes')

        elif isinstance(self.mask_background, str) or isinstance(self.mask_background, np.ndarray):

            return raster_tools.create_raster(self.out_image_temp,
                                              self.o_info,
                                              compress='none',
                                              tile=False)

        else:

            return raster_tools.create_raster(self.output_image,
                                              self.o_info,
                                              tile=False)

    def _set_n_blocks(self,
                      start_i,
                      start_j,
                      iwo,
                      jwo,
                      rows,
                      cols,
                      block_rows,
                      block_cols):

        if self.relax_probabilities or self.morphology:
            pad = self.plr_window_size  # int(self.plr_window_size / 2.0)
        else:
            pad = 0

        block_indices = list()

        n_blocks = 0

        for i_ in range(start_i, rows+iwo, block_rows):

            n_rows_ = self._num_rows_cols(i_, block_rows, rows+iwo)

            # Always =i if pad=0
            iw_ = 0 if i_ == 0 else i_ - pad
            ipadded_ = i_ - iw_
            rww_ = n_rows_ + pad if iw_ == 0 else n_rows_ + (pad * 2)
            rw_ = self._num_rows_cols(iw_, rww_, rows+iwo)

            for j_ in range(start_j, cols+jwo, block_cols):

                n_cols_ = self._num_rows_cols(j_, block_cols, cols+jwo)

                jw_ = 0 if j_ == 0 else j_ - pad
                jpadded_ = j_ - jw_
                cww_ = n_cols_ + pad if jw_ == 0 else n_cols_ + (pad * 2)
                cw_ = self._num_rows_cols(jw_, cww_, cols+iwo)

                block_indices.append((i_, j_, n_rows_, n_cols_, iw_, jw_, rw_, cw_, pad, ipadded_, jpadded_))

                n_blocks += 1

        return block_indices, n_blocks

    def _mask_background(self):

        """
        Recodes background values to zeros

        Returns:
            None, writes to ``self.output_image``.
        """

        if isinstance(self.mask_background, str):
            b_info = raster_tools.ropen(self.mask_background)

        with raster_tools.ropen(self.out_image_temp) as m_info:

            m_info.get_band(1)
            m_info.storage = 'byte'

            out_rst_object = raster_tools.create_raster(self.output_image,
                                                        m_info,
                                                        compress='none',
                                                        tile=False)

            out_rst_object.get_band(1)

            b_rows, b_cols = m_info.rows, m_info.cols

            block_rows, block_cols = raster_tools.block_dimensions(b_rows,
                                                                   b_cols,
                                                                   row_block_size=self.row_block_size,
                                                                   col_block_size=self.col_block_size)

            for i in range(0, b_rows, block_rows):

                n_rows = self._num_rows_cols(i, block_rows, b_rows)

                for j in range(0, b_cols, block_cols):

                    n_cols = self._num_rows_cols(j, block_cols, b_cols)

                    m_array = m_info.read(i=i,
                                          j=j,
                                          rows=n_rows,
                                          cols=n_cols,
                                          d_type='byte')

                    # Get the background array.
                    if isinstance(self.mask_background, str):

                        b_array = raster_tools.read(i_info=b_info,
                                                    bands2open=self.background_band,
                                                    x=m_info.left+(j*m_info.cell.Y),
                                                    y=m_info.top-(i*m_info.cellY),
                                                    rows=n_rows,
                                                    cols=n_cols,
                                                    d_type='byte')

                    else:
                        b_array = self.mask_background[i:i+n_rows, j:j+n_cols]

                    m_array[b_array == self.background_value] = 0

                    if self.minimum_observations > 0:

                        # Get the observation counts array.
                        observation_array = raster_tools.read(i_info=b_info,
                                                              bands2open=self.observation_band,
                                                              i=i,
                                                              j=j,
                                                              rows=n_rows,
                                                              cols=n_cols,
                                                              d_type='byte')

                        m_array[observation_array < self.minimum_observations] = 0

                    out_rst_object.write_array(m_array, i, j)

        m_info = None

        if isinstance(self.mask_background, str):

            b_info.close()
            b_info = None

        out_rst_object.close_all()
        out_rst_object = None

        os.remove(self.out_image_temp)

    @staticmethod
    def _num_rows_cols(pixel_index, block_size, rows_cols):
        return block_size if (pixel_index + block_size) < rows_cols else rows_cols - pixel_index

    def _get_feas(self, img_obj_list, i, j, n_rows, n_cols):

        if self.use_xy:

            x_coordinates, y_coordinates = self._create_indices(i, j, n_rows, n_cols)

            feature_arrays = [x_coordinates, y_coordinates]

        else:

            feature_arrays = list()

        # for bd in range(0, self.i_info.bands):
        for iol in img_obj_list:

            if iol[-1]:

                __, __, start_j, start_i = vector_tools.get_xy_offsets(image_info=self.i_info, xy_info=iol[1])

            else:

                start_j, start_i = 0, 0

            # print start_j, start_i
            # sys.exit()

            # if iol[3] > self.i_info.cellY:
            #
            #     n_cols_coarse = int((n_cols * self.i_info.cellY) / iol[3])
            #     n_rows_coarse = int((n_rows * self.i_info.cellY) / iol[3])
            #
            #     coarse_array = iol[0].ReadAsArray(iol[1]+j, [2]+i, n_cols_coarse, n_rows_coarse).astype(np.float32)
            #
            #     row_zoom_factor = n_rows / float(n_rows_coarse)
            #     col_zoom_factor = n_cols / float(n_cols_coarse)
            #
            #     feature_array = zoom(coarse_array, (row_zoom_factor, col_zoom_factor), order=2)
            #
            # else:

            feature_arrays.append(iol[0].ReadAsArray(start_j+j, start_i+i, n_cols, n_rows).astype(np.float32))

        return np.vstack(feature_arrays).reshape(self.i_info.bands, n_rows, n_cols)

        # return np.vstack([img_obj_list[bd][0].ReadAsArray(img_obj_list[bd][1]+j, img_obj_list[bd][2]+i,
        #                                                   n_cols, n_rows).astype(np.float32) for bd in
        #                   range(0, self.i_info.bands)]).reshape(self.i_info.bands, n_rows, n_cols)

    def _get_additional_layers(self, i, j, n_rows, n_cols):

        """
        Gets additional image layers

        Args:
            i (int)
            j (int)
            n_rows (int)
            n_cols (int)
        """

        additional_stack = None

        for additional_layer in self.additional_layers:

            with raster_tools.ropen(additional_layer) as a_info:

                if isinstance(additional_stack, np.ndarray):

                    additional_stack_ = a_info.read(bands2open=-1,
                                                    i=i,
                                                    j=j,
                                                    rows=n_rows,
                                                    cols=n_cols,
                                                    d_type='float32').ravel()[:, np.newaxis]

                    additional_stack = np.hstack((additional_stack,
                                                  additional_stack_))

                else:

                    additional_stack = a_info.read(bands2open=-1,
                                                   i=i,
                                                   j=j,
                                                   rows=n_rows,
                                                   cols=n_cols,
                                                   d_type='float32').ravel()[:, np.newaxis]

            a_info = None

        return additional_stack

    def _create_indices(self, i, j, n_rows, n_cols):

        """
        Creates x,y coordinate indices

        Args:
            i (int)
            j (int)
            n_rows (int)
            n_cols (int)
        """

        left = self.i_info.left + (j * self.i_info.cellY)
        top = self.i_info.top - (i * self.i_info.cellY)

        # Create the longitudes
        x_coordinates = np.arange(left,
                                  left + (self.i_info.cellY * n_cols),
                                  self.i_info.cellY)

        x_coordinates = np.tile(x_coordinates, n_rows).reshape(n_rows, n_cols)

        # Create latitudes
        y_coordinates = np.arange(top,
                                  top - (self.i_info.cellY * n_rows),
                                  -self.i_info.cellY).reshape(n_rows, 1)

        y_coordinates = np.tile(y_coordinates, n_cols)

        return x_coordinates.ravel()[:, np.newaxis], y_coordinates.ravel()[:, np.newaxis]

    @staticmethod
    def _get_slope(elevation_array, pad=50):

        elevation_array = cv2.copyMakeBorder(elevation_array, pad, pad, pad, pad, cv2.BORDER_REFLECT)

        x_grad, y_grad = np.gradient(elevation_array)

        return (np.pi / 2.0) - np.arctan(np.sqrt((x_grad * x_grad) + (y_grad * y_grad)))

    def test_accuracy(self, out_acc=None, discrete=True, be_quiet=False):

        """
        Tests the accuracy of a model (a model must be trained or loaded).

        Args:
            out_acc (str): The output name of the accuracy text file.
            discrete (Optional[bool]): Whether the accuracy should assume discrete data.
                Otherwise, assumes continuous. Default is True.
            be_quiet (Optional[bool]): Whether to be quiet and do not print to screen. Default is False.

        Returns:
            None, writes to ``out_acc`` if given, and prints results to screen.

        Examples:
            >>> # get test accuracy
            >>> cl.test_accuracy(out_acc='/out_accuracy.txt')
            >>> print(cl.emat.accuracy)
        """

        if self.classifier_info['classifier'] == 'cvmlp':

            test_labs_pred = np.empty((self.p_vars_test_rows, self.n_classes), dtype='uint8')
            self.model.predict(self.p_vars_test, test_labs_pred)
            test_labs_pred = np.argmax(test_labs_pred, axis=1)

        elif 'CV' in self.classifier_info['classifier']:

            if (0 < self.perc_samp_each < 1) or ((self.perc_samp_each == 0) and (0 < self.perc_samp < 1)):
                __, test_labs_pred = self.model.predict(self.p_vars_test)
            else:
                __, test_labs_pred = self.model.predict(self.p_vars)

        elif self.classifier_info['classifier'] in ['c5', 'cubist']:

            if (0 < self.perc_samp_each < 1) or ((self.perc_samp_each == 0) and (0 < self.perc_samp < 1)):

                features = ro.r.matrix(self.p_vars_test, nrow=self.p_vars_test.shape[0],
                                       ncol=self.p_vars_test.shape[1])
            else:

                features = ro.r.matrix(self.p_vars, nrow=self.p_vars.shape[0],
                                       ncol=self.p_vars.shape[1])

            features.colnames = StrVector(self.headers[:-1])

            test_labs_pred = _do_c5_cubist_predict(self.model, self.classifier_info['classifier'],
                                                   features)

        else:

            if isinstance(self.p_vars_test, np.ndarray):
                test_labs_pred = self.model.predict(self.p_vars_test)
            else:

                # Test the train variables if no test variables exist.
                test_labs_pred = self.model.predict(self.p_vars)

        if isinstance(self.p_vars_test, np.ndarray):

            if discrete:
                self.test_array = np.int16(np.c_[test_labs_pred, self.labels_test])
            else:
                self.test_array = np.float32(np.c_[test_labs_pred, self.labels_test])

        else:

            if discrete:
                self.test_array = np.int16(np.c_[test_labs_pred, self.labels])
            else:
                self.test_array = np.float32(np.c_[test_labs_pred, self.labels])

        if not be_quiet:
            logger.info('  Getting test accuracy ...')

        self.emat = error_matrix()

        self.emat.get_stats(po_array=self.test_array,
                            discrete=discrete)

        if out_acc:
            self.emat.write_stats(out_acc)

    def recursive_elimination(self, method='rf', perc_samp_each=.5):

        """
        Recursively eliminates features.

        Args:
            method (Optional[str]): The method to use. Default is 'rf'. Choices are ['rf', 'chi2'].
            perc_samp_each (Optional[float]): The percentage to sample at each iteration. Default is .5. 

        Returns:
            None, plots results.

        Examples:
            >>> import mpglue as gl
            >>>
            >>> cl = gl.classification()
            >>>
            >>> cl.split_samples('/samples.txt', perc_samp=1.)
            >>> cl.construct_model(classifier_info={'classifier': 'rf', 'trees': 500})
            >>> cl.recursive_elimination()
        """

        if method == 'chi2':

            if not hasattr(self, 'p_vars'):

                logger.error('  Be sure to run `split_samples` to create the `p_vars` variables.')
                raise AttributeError

            if not hasattr(self, 'labels'):

                logger.error('  Be sure to run `split_samples` to create the `labels` variables.')
                raise AttributeError

            p_vars = self.p_vars.copy()

            # Scale negative values to positive (for Chi Squared)
            for var_col_pos in range(0, p_vars.shape[1]):

                col_min = p_vars[:, var_col_pos].min()

                if col_min < 0:
                    p_vars[:, var_col_pos] = np.add(p_vars[:, var_col_pos], abs(col_min))

            feas_ranked, p_val = chi2(p_vars, self.labels)

        elif method == 'rf':

            if not hasattr(self, 'model'):
                logger.error('  A RF model must be trained to use RF feature importance.')

            if not hasattr(self.model, 'feature_importances_'):
                logger.error('  A RF model must be trained to use RF feature importance.')

            feas_ranked = self.model.feature_importances_

        else:
            logger.error('  The feature ranking method is not supported.')
            raise NameError

        loop_len = len(feas_ranked) + 1

        feas_ranked[np.isnan(feas_ranked)] = 0.

        self.fea_rank = dict()

        for i in range(1, loop_len):
            self.fea_rank[i] = feas_ranked[i-1]

        indices = list()
        indice_counts = list()
        accuracy_scores = list()

        for i, s in enumerate(sorted(self.fea_rank, key=self.fea_rank.get)):

            if (len(self.fea_rank) - i) <= (len(self.classes) * 2):

                break

            else:

                indices.append(s)

                self.split_samples(self.file_name,
                                   perc_samp_each=perc_samp_each,
                                   ignore_feas=indices,
                                   use_xy=self.use_xy)

                logger.info('  {:d} features ...'.format(self.n_feas))

                self.construct_model(classifier_info=self.classifier_info)

                self.test_accuracy()

                # print 'Overall accuracy: {:.2f}'.format(self.emat.accuracy)
                # print 'Kappa score: {:.2f}\n'.format(self.emat.kappa_score)

                indice_counts.append(len(indices))
                accuracy_scores.append(self.emat.accuracy)

        accuracy_scores_sm = [sum(accuracy_scores[r:r+3]) / 3. for r in range(0, len(accuracy_scores)-2)]
        accuracy_scores_sm.insert(0, sum(accuracy_scores_sm[:2]) / 2.)
        accuracy_scores_sm.append(sum(accuracy_scores_sm[-2:]) / 2.)

        plt.plot(indice_counts, accuracy_scores_sm)
        plt.xlabel('Number of features removed')
        plt.ylabel('Overall accuracy')
        plt.show()

        plt.close()

    def rank_feas(self, rank_text=None, rank_method='chi2', top_feas=1., be_quiet=False):

        """
        Ranks image features by importance.

        Args:
            rank_text (Optional[str]): A text file to write ranked features to. Default is None.
            rank_method (Optional[str]): The method to use for feature ranking. Default is 'chi2' (Chi^2). Choices are 
                ['chi2', 'rf'].
            top_feas (Optional[float or int]): The percentage or total number of features to reduce to. 
                Default is 1., or no reduction.
            be_quiet (Optional[bool]): Whether to be quiet and do not print to screen. Default is False.

        Returns:
            None, writes to ``rank_text`` if given and prints results to screen.

        Examples:
            >>> # rank image features
            >>> cl.split_samples('/samples.txt', scale_data=True)
            >>> cl.rank_feas(rank_text='/ranked_feas.txt',
            >>>              rank_method='chi2', top_feas=.2)
            >>> print cl.fea_rank
            >>>
            >>> # a RF model must be trained before feature ranking
            >>> cl.construct_model()
            >>> cl.rank_feas(rank_method='rf', top_feas=.5)
        """

        if isinstance(rank_text, str):

            d_name, f_name = os.path.split(rank_text)

            if not os.path.isdir(d_name):
                os.makedirs(d_name)

            rank_txt_wr = open(rank_text, 'wb')

        if rank_method == 'chi2':

            if not hasattr(self, 'p_vars'):

                logger.error('  Be sure to run `split_samples` to create the `p_vars` variables.')
                raise AttributeError

            if not hasattr(self, 'labels'):

                logger.error('  Be sure to run `split_samples` to create the `labels` variables.')
                raise AttributeError

            p_vars = self.p_vars.copy()

            # Scale negative values to positive (for Chi Squared)
            for var_col_pos in range(0, p_vars.shape[1]):

                col_min = p_vars[:, var_col_pos].min()

                if col_min < 0:
                    p_vars[:, var_col_pos] = np.add(p_vars[:, var_col_pos], abs(col_min))

            feas_ranked, p_val = chi2(p_vars, self.labels)

            loop_len = len(feas_ranked) + 1

        elif rank_method == 'rf':

            if not hasattr(self, 'model'):
                logger.error('  A RF model must be trained to use RF feature importance.')

            if not hasattr(self.model, 'feature_importances_'):
                logger.error('  A RF model must be trained to use RF feature importance.')

            feas_ranked = self.model.feature_importances_

            loop_len = len(feas_ranked) + 1

        else:

            logger.error('  The feature ranking method is not supported.')
            raise NameError

        feas_ranked[np.isnan(feas_ranked)] = 0.

        self.fea_rank = dict()

        for i in range(1, loop_len):
            self.fea_rank[i] = feas_ranked[i-1]

        if rank_method == 'chi2':
            title = '**********************\n*                    *\n* Chi^2 Feature Rank *\n*                    *\n**********************\n\nRank      Variable      Value\n----      --------      -----'
        elif rank_method == 'rf':
            title = '************************************\n*                                  *\n* Random Forest Feature Importance *\n*                                  *\n************************************\n\nRank      Variable      Value\n----      --------      -----'

        if not be_quiet:
            logger.info(title)

        if isinstance(rank_text, str):
            rank_txt_wr.write('%s\n' % title)

        if isinstance(top_feas, float):
            n_best_feas = int(top_feas * len(self.fea_rank))
        elif isinstance(top_feas, int):
            n_best_feas = copy(top_feas)

        r = 1
        self.bad_features = list()

        for s in sorted(self.fea_rank, key=self.fea_rank.get, reverse=True):

            if r <= n_best_feas:

                if r < 10 and s < 10:
                    ranks = '%d         %d             %s' % (r, s, str(self.fea_rank[s]))
                elif r >= 10 and s < 10:
                    ranks = '%d        %d             %s' % (r, s, str(self.fea_rank[s]))
                elif r < 10 and s >= 10:
                    ranks = '%d         %d            %s' % (r, s, str(self.fea_rank[s]))
                else:
                    ranks = '%d        %d            %s' % (r, s, str(self.fea_rank[s]))

                if not be_quiet:
                    logger.info(ranks)

                if isinstance(rank_text, str):
                    rank_txt_wr.write('%s\n' % ranks)

            else:
                # append excluded variables and remove from the "good" variables
                self.bad_features.append(s)

                del self.fea_rank[s]

            r += 1

        self.ranked_feas = np.array(sorted(self.fea_rank, key=self.fea_rank.get, reverse=True))

        if not be_quiet:

            logger.info('  Mean score:  %.2f' % np.average([v for k, v in viewitems(self.fea_rank)]))

            logger.info('  ==================')
            logger.info('  Excluded variables')
            logger.info('  ==================')
            logger.info(','.join(list(map(str, sorted(self.bad_features)))))

        if isinstance(rank_text, str):

            rank_txt_wr.write('\n==================\n')
            rank_txt_wr.write('Excluded variables\n')
            rank_txt_wr.write('==================\n')
            rank_txt_wr.write(','.join([str(bf) for bf in sorted(self.bad_features)]))
            rank_txt_wr.close()

    def add_variable_names(self, layer_names, stat_names, additional_features=[]):

        """
        Adds band-stat name pairs.

        Args:
            layer_names (list): A list of layer names.
            stat_names (list): A list of statistics names.
            additional_features (Optional[list]): Additional features. Default is [].

        Examples:
            >>> import mpglue as gl
            >>>
            >>> cl = gl.classification()
            >>>
            >>> cl.add_variable_names(['NDVI', 'EVI2', 'GNDVI', 'NDWI', 'NDBaI'],
            >>>                       ['min', 'max', 'median', 'cv', 'jd', 'slopemx', 'slopemn'],
            >>>                       additional_features=['x', 'y'])
            >>>
            >>> # get the 10th variable
            >>> cl.variable_names[10]
        """

        counter = 1
        self.variable_names = dict()

        for layer_name in layer_names:

            for stat_name in stat_names:

                self.variable_names[counter] = '{} {}'.format(layer_name, stat_name)

                counter += 1

        if additional_features:

            for additional_feature in additional_features:

                self.variable_names[counter] = additional_feature

                counter += 1

        for k, v in viewitems(self.variable_names):
            logger.info(k, v)

    def sub_feas(self, input_image, out_img, band_list=None):

        """
        Subsets features. 

        Args:
            input_image (str): Full path, name, and extension of a single image.
            out_img (str): The output image.
            band_list (Optional[list]): A list of bands to subset. Default is []. If empty, ``sub_feas`` subsets 
                the top n best features returned by ``rank_feas``.

        Returns:
            None, writes to ``out_img``.

        Examples:
            >>> import mpglue as gl
            >>>
            >>> cl = gl.classification()
            >>>
            >>> cl.split_samples('/samples.txt', scale_data=True)
            >>> cl.rank_feas(rank_method='chi2', top_feas=.2)
            >>>
            >>> # apply feature rank to subset a feature image using cl.ranked_feas
            >>> cl.sub_feas('/in_image.vrt', '/ranked_feas.vrt')
        """

        if not hasattr(self, 'ranked_feas'):
            sys.exit('\nERROR!! The features need to be ranked first. See <rank_feas> method.\n')

        if not isinstance(input_image, str):
            sys.exit('\nERROR!! The input image needs to be specified in order set the extent.\n')

        if not os.path.isfile(input_image):
            sys.exit('\nERROR!! %s does not exist.\n' % input_image)

        d_name, f_name = os.path.split(out_img)
        f_base, f_ext = os.path.splitext(f_name)

        if not os.path.isdir(d_name):
            os.makedirs(d_name)

        if 'vrt' not in f_ext.lower():

            out_img_orig = copy(out_img)
            out_img = '%s/%s.vrt' % (d_name, f_base)

        if not band_list:

            # create the band list
            band_list = ''
            for fea_idx in self.ranked_feas:
                band_list = '%s-b %d ' % (band_list, fea_idx)

        logger.info('  Subsetting ranked features ...')

        com = 'gdalbuildvrt %s %s %s' % (band_list, out_img, input_image)

        subprocess.call(com, shell=True)

        if 'tif' in f_ext.lower():

            com = 'gdal_translate --config GDAL_CACHEMAX 256 -of GTiff -co TILED=YES -co COMPRESS=LZW %s %s' % \
                  (out_img, out_img_orig)

            subprocess.call(com, shell=True)

        elif 'img' in f_ext.lower():

            com = 'gdal_translate --config GDAL_CACHEMAX 256 -of HFA -co COMPRESS=YES %s %s' % \
                  (out_img, out_img_orig)

            subprocess.call(com, shell=True)

    def grid_search_gridcrf(self, classifier_parameters, method='overall', output_file=None):

        """
        Conditional Random Field SSVM parameter grid search

        Args:
            classifier_name (str): The classifier to optimize.
            classifier_parameters (dict): The classifier parameters.
            method (Optional[str]): The score method to use, 'overall' (default) or 'f1'. Choices are ['overall', 'f1'].
            output_file (Optional[str]):

        Examples:
            >>> cl.load4crf(var_image_list, cdl_labels_list)
            >>>
            >>> cl.grid_search_gridcrf(dict(max_iter=[100, 500, 1000],
            >>>                             C=[.001, .01, .1, 1, 10, 100],
            >>>                             tol=[.001, .01, .1],
            >>>                             inference_cache=[0, 100],
            >>>                             neighborhood=[4, 8]))
        """

        param_order = list(classifier_parameters)

        # Setup the output scores table.
        df_param_headers = '-'.join(list(classifier_parameters))
        df = pd.DataFrame(columns=[df_param_headers])
        df[df_param_headers] = list(itertools.product(*itervalues(classifier_parameters)))

        # Setup the error object.
        emat = error_matrix()

        # Iterate over all possible parameter combinations.
        for param_combo in list(itertools.product(*itervalues(classifier_parameters))):

            # Set the current parameters.
            current_combo = dict(zip(param_order, param_combo))

            # Add the classifier name to the dictionary.
            current_combo['classifier'] = 'gridcrf'
            current_combo['n_jobs'] = -1

            # Train the model.
            self.construct_model(classifier_info=current_combo)

            # Make predictions
            combo_predictions = np.array(self.model.predict(self.p_vars), dtype='uint8')

            # Get the model accuracy.
            emat.get_stats(po_array=np.c_[combo_predictions.ravel(),
                                          self.labels.ravel()])

            if method == 'overall':
                df.loc[df[df_param_headers] == param_combo, 'Accuracy'] = emat.accuracy

            logger.info(param_combo)
            logger.info(df)
            logger.info(emat.accuracy)

        best_score_index = np.argmax(df['Accuracy'].values)

        logger.info('  Best score: {:f}'.format(df['Accuracy'].values[best_score_index]))

        logger.info('  Best parameters:')
        logger.info(''.join(['='] * len(df_param_headers)))
        logger.info(df_param_headers)
        logger.info(''.join(['='] * len(df_param_headers)))
        logger.info(df[df_param_headers].values[best_score_index])

        if isinstance(output_file, str):
            df.to_csv(output_file, sep=',', index=False)

        return df

    def grid_search(self, classifier_name, classifier_parameters, file_name, k_folds=3,
                    perc_samp=.5, ignore_feas=[], use_xy=False, classes2remove=[],
                    method='overall', metric='accuracy', f1_class=0, stratified=False, spacing=1000.,
                    output_file=None, calibrate_proba=False):

        """
        Classifier parameter grid search

        Args:
            classifier_name (str): The classifier to optimize.
            classifier_parameters (dict): The classifier parameters.
            file_name (str): The sample file name.
            k_folds (Optional[int]): The number of cross-validation folds. Default is 3.
            perc_samp (Optional[float]): The percentage of samples to take at each fold. Default is .5.
            ignore_feas (Optional[int list]): A list of features to ignore. Default is [].
            use_xy (Optional[bool]): Whether to use x, y coordinates. Default is False.
            classes2remove (Optional[int list]): A list of classes to remove. Default is [].
            method (Optional[str]): The score method to use, 'overall' (default) or 'f1'. Choices are ['overall', 'f1'].
            metric (Optional[str]): The scoring metric to use. Default is 'accuracy'.
                Choices are ['accuracy', 'r_squared', 'rmse', 'mae', 'medae', 'mse'].
            f1_class (Optional[int]): The class position to evaluate when ``method`` is equal to 'f1'. Default is 0,
                or first index position.
            stratified (Optional[bool]):
            spacing (Optional[float]):
            output_file (Optional[str]):

        Returns:
            DataFrame with scores.
        """

        regressors = ['cubist', 'rfr', 'abr', 'bag-dtr', 'ex-rfr', 'ex-dtr', 'dtr']

        if metric not in ['accuracy', 'r_squared', 'rmse', 'mae', 'medae', 'mse']:

            logger.error('  The metric is not supported.')
            raise NameError

        if classifier_name in regressors and metric == 'accuracy':

            logger.error('  Overall accuracy is not supported with regression classifiers.')
            raise NameError

        if classifier_name not in regressors and metric in ['r_squared', 'rmse', 'mae', 'medae', 'mse']:

            logger.error('  Overall accuracy is the only option with discrete classifiers.')
            raise NameError

        if classifier_name in ['c5', 'cubist']:

            if 'R_installed' not in globals():

                logger.warning('  You must use `classification_r` to use C5 and Cubist.')
                return

            if not R_installed:

                logger.warning('  R and rpy2 must be installed to use C5 or Cubist.')
                return

        if classifier_name in regressors:
            discrete = False
        else:
            discrete = True

        score_label = metric.upper()

        param_order = list(classifier_parameters)

        df_param_headers = '-'.join(param_order)
        df_fold_headers = ('F' + '-F'.join(list(map(str, range(1, k_folds+1))))).split('-')

        # Setup the output scores table.
        df = pd.DataFrame(columns=df_fold_headers)
        df[df_param_headers] = list(itertools.product(*itervalues(classifier_parameters)))

        # Open the weights file.
        lc_weights = file_name.replace('.txt', '_w.txt')

        if os.path.isfile(lc_weights):
            weights = self.load(lc_weights)
        else:
            weights = None

        for k_fold in range(1, k_folds+1):

            logger.info('  Fold {:d} of {:d} ...'.format(k_fold, k_folds))

            self.split_samples(file_name, perc_samp_each=perc_samp, ignore_feas=ignore_feas,
                               use_xy=use_xy, classes2remove=classes2remove, stratified=stratified,
                               spacing=spacing, sample_weight=weights)

            if classifier_name in ['c5', 'cubist']:

                predict_samps = ro.r.matrix(self.p_vars, nrow=self.n_samps, ncol=self.n_feas)
                predict_samps.colnames = StrVector(self.headers[:-1])

            # Iterate over all possible combinations.
            for param_combo in list(itertools.product(*itervalues(classifier_parameters))):

                # Set the current parameters.
                current_combo = dict(zip(param_order, param_combo))

                # Add the classifier name to the dictionary.
                current_combo['classifier'] = classifier_name

                if classifier_name in ['c5', 'cubist']:
                    self.construct_r_model(classifier_info=current_combo)
                else:
                    self.construct_model(classifier_info=current_combo,
                                         calibrate_proba=calibrate_proba)

                # Get the accuracy
                self.test_accuracy(discrete=discrete)

                if method == 'overall':
                    df.loc[df[df_param_headers] == param_combo, 'F{:d}'.format(k_fold)] = getattr(self.emat, metric)

                elif method == 'f1':
                    df.loc[df[df_param_headers] == param_combo, 'F{:d}'.format(k_fold)] = self.emat.f_scores[f1_class]

        df[score_label] = df[df_fold_headers].mean(axis=1)

        if metric in ['accuracy', 'r_squared']:
            best_score_index = np.argmax(df[score_label].values)
        else:
            best_score_index = np.argmin(df[score_label].values)

        logger.info('  Best {} score: {:f}'.format(metric, df[score_label].values[best_score_index]))

        logger.info('  Best parameters:')
        logger.info(''.join(['='] * len(df_param_headers)))
        logger.info(df_param_headers)
        logger.info(''.join(['=']*len(df_param_headers)))
        logger.info(df[df_param_headers].values[best_score_index])

        if isinstance(output_file, str):
            df.to_csv(output_file, sep=',', index=False)

        return df

    def optimize_parameters(self,
                            file_name,
                            classifier_info={'classifier': 'rf'},
                            n_trees_list=[500, 1000, 1500, 2000],
                            trials_list=[2, 5, 10],
                            max_depth_list=[25, 30, 35, 40, 45, 50],
                            min_samps_list=[2, 5, 10],
                            criterion_list=['gini'],
                            rand_vars_list=['sqrt'],
                            cf_list=[.25, .5, .75],
                            committees_list=[1, 2, 5, 10],
                            rules_list=[25, 50, 100, 500],
                            extrapolation_list=[0, 1, 5, 10],
                            class_weight_list=[None, 'balanced', 'balanced_subsample'],
                            learn_rate_list=[.1, .2, .4, .6, .8, 1.],
                            bool_list=[True, False],
                            c_list=[1., 10., 20., 100.],
                            gamma_list=[.001, .001, .01, .1, 1., 5.],
                            k_folds=3,
                            perc_samp=.5,
                            ignore_feas=[],
                            use_xy=False,
                            classes2remove=[],
                            method='overall',
                            f1_class=0,
                            stratified=False,
                            spacing=1000.,
                            calibrate_proba=False,
                            output_file=None):

        """
        Finds the optimal parameters for a classifier by training and testing a range of classifier parameters
        by n-folds cross-validation.

        Args:
            file_name (str): The file name of the samples.
            classifier_info (Optional[dict]): The model parameters dictionary. Default is {'classifier': 'rf'}.
            n_trees_list (Optional[int list]): A list of trees. Default is [500, 1000].
            trials_list (Optional[int list]): A list of boosting trials. Default is [5, 10, 20].
            max_depth_list (Optional[int list]): A list of maximum depths. Default is [5, 10, 20, 25, 30, 50].
            min_samps_list (Optional[int list]): A list of minimum samples. Default is [2, 5, 10].
            criterion_list (Optional[str list]): A list of RF criterion. Default is ['gini', 'entropy'].
            rand_vars_list (Optional[str list]): A list of random variables. Default is ['sqrt'].
            class_weight_list (Optional[bool]): A list of class weights.
                Default is [None, 'balanced', 'balanced_subsample'].
            c_list (Optional[float list]): A list of SVM C parameters. Default is [1., 10., 20., 100.].
            gamma_list (Optional[float list]): A list of SVM gamma parameters. Default is [.001, .001, .01, .1, 1., 5.].
            k_folds (Optional[int]): The number of N cross-validation folds. Default is 3.
            ignore_feas (Optional[int list]): A list of features to ignore. Default is [].
            use_xy (Optional[bool]): Whether to use x, y coordinates. Default is False.
            classes2remove (Optional[int list]): A list of classes to remove. Default is [].
            method (Optional[str]): The score method to use, 'overall' (default) or 'f1'.1
            f1_class (Optional[int]): The class position to evaluate when ``method`` is equal to 'f1'. Default is 0,
                or first index position.
            stratified (Optional[bool]):
            spacing (Optional[float]):
            output_file (Optional[str]):

        Returns:
            `Pandas DataFrame` when classifier_info['classifier'] == 'c5',
                otherwise None, prints results to screen.

        Examples:
            >>> # find the optimal parameters (max depth, min samps, trees)
            >>> # randomly sampling 50% (with replacement) and testing on the 50% set aside
            >>> # repeat 5 (k_folds) times and average the results
            >>> import mpglue as gl
            >>>
            >>> cl = gl.classification()
            >>>
            >>> # Find the optimum parameters for an Extremely Randomized Forest.
            >>> cl.optimize_parameters('/samples.txt',
            >>>                        classifier_info={'classifier': 'ex-rf'},
            >>>                        use_xy=True)
            >>>
            >>> # Find the optimum parameters for a Random Forest, but assess
            >>> #   only one class (1st class position) of interest.
            >>> cl.optimize_parameters('/samples.txt',
            >>>                        classifier_info={'classifier': 'rf'},
            >>>                        use_xy=True, method='f1', f1_class=0)
            >>>
            >>> # Optimizing C5 parameters
            >>> from mpglue.classifiers import classification_r
            >>>
            >>> cl = classification_r()
            >>>
            >>> df = cl.optimize_parameters('/samples.txt', classifier_info={'classifier': 'c5'},
            >>>                             trials_list=[2, 5, 10], cf_list=[.25, .5, .75],
            >>>                             min_samps_list=[2, 5, 10], bool_list=[True, False],
            >>>                             k_folds=5, stratified=True, spacing=50000.)
            >>>
            >>> print df
        """

        if classifier_info['classifier'] not in ['c5', 'cubist']:

            self.split_samples(file_name, perc_samp=1., ignore_feas=ignore_feas,
                               use_xy=use_xy, classes2remove=classes2remove)

            prediction_models = {'rf': ensemble.RandomForestClassifier(n_jobs=-1),
                                 'rfr': ensemble.RandomForestRegressor(n_jobs=-1),
                                 'ex-rf': ensemble.ExtraTreesClassifier(n_jobs=-1),
                                 'ex-rfr': ensemble.ExtraTreesRegressor(n_jobs=-1),
                                 'bag-dt': ensemble.BaggingClassifier(base_estimator=tree.DecisionTreeClassifier(),
                                                                      n_jobs=-1),
                                 'ab-dt': ensemble.AdaBoostClassifier(base_estimator=tree.DecisionTreeClassifier()),
                                 'gb': ensemble.GradientBoostingClassifier(),
                                 'dt': tree.DecisionTreeClassifier()}

        if classifier_info['classifier'] in ['rf', 'ex-rf']:
            #print("Entro a optimizar")                
            parameters = {'criterion': criterion_list,
                          'n_estimators': n_trees_list,
                          'max_depth': max_depth_list,
                          'max_features': rand_vars_list,
                          'min_samples_split': min_samps_list,
                          'class_weight': class_weight_list}

        elif classifier_info['classifier'] in ['rfr', 'ex-rfr', 'dtr']:

            parameters = {'trees': n_trees_list,
                          'max_depth': max_depth_list,
                          'rand_vars': rand_vars_list,
                          'min_samps': min_samps_list}

        elif classifier_info['classifier'] in ['ab-dt', 'ab-dt', 'ab-ex-dt', 'ab-rf', 'ab-ex-rf']:

            parameters = {'n_estimators': n_trees_list,
                          'trials': trials_list,
                          'learning_rate': learn_rate_list,
                          'max_depth': max_depth_list,
                          'min_samps': min_samps_list,
                          'class_weight': class_weight_list}

        elif classifier_info['classifier'] in ['abr', 'abr-ex-dtr']:

            parameters = {'trees': n_trees_list,
                          'rate': learn_rate_list}

        elif classifier_info['classifier'] == 'bag-dt':

            parameters = {'n_estimators': n_trees_list,
                          'warm_start': bool_list,
                          'bootstrap': bool_list,                          
                          'bootstrap_features': bool_list}

        elif classifier_info['classifier'] == 'bag-dtr':

            parameters = {'trees': n_trees_list,
                          'warm_start': bool_list,
                          'bootstrap': bool_list,
                          'bootstrap_features': bool_list}

        elif classifier_info['classifier'] == 'gb':

            parameters = {'n_estimators': n_trees_list,
                          'max_depth': max_depth_list,
                          'max_features': rand_vars_list,
                          'min_samples_split': min_samps_list,
                          'learning_rate': learn_rate_list}

        elif classifier_info['classifier'] == 'gbr':

            parameters = {'trees': n_trees_list,
                          'max_depth': max_depth_list,
                          'rand_vars': rand_vars_list,
                          'min_samps': min_samps_list,
                          'learning_rate': learn_rate_list}

        elif classifier_info['classifier'] == 'dt':

            parameters = {'n_estimators': n_trees_list,
                          'max_depth': max_depth_list,
                          'max_features': rand_vars_list,
                          'min_samples_split': min_samps_list}

        elif classifier_info['classifier'] == 'svmc':

            parameters = {'C': c_list,
                          'gamma': gamma_list}

        elif classifier_info['classifier'] == 'c5':

            parameters = {'trials': trials_list,
                          'min_cases': min_samps_list,
                          'CF': cf_list,
                          'fuzzy': bool_list}

        elif classifier_info['classifier'] == 'cubist':

            parameters = {'committees': committees_list,
                          'rules': rules_list,
                          'extrapolation': extrapolation_list,
                          'unbiased': bool_list}

        else:

            logger.error('  The model cannot be optimized.')
            return NameError

        logger.info('  Finding the best paramaters for a {} model ...'.format(classifier_info['classifier']))

        core_classifiers = ['c5', 'cubist', 'rf', 'rfr',
                            'ab-rf', 'ab-ex-rf', 'ab-dt', 'ab-ex-dt',
                            'abr', 'bag-dtr', 'ex-rf', 'ex-rfr', 'ex-dtr', 'dtr']

        if classifier_info['classifier'] in core_classifiers:

            return self.grid_search(classifier_info['classifier'],
                                    parameters,
                                    file_name,
                                    k_folds=k_folds,
                                    perc_samp=perc_samp,
                                    ignore_feas=ignore_feas,
                                    use_xy=use_xy,
                                    classes2remove=classes2remove,
                                    method=method,
                                    f1_class=f1_class,
                                    stratified=stratified,
                                    spacing=spacing,
                                    output_file=output_file,
                                    calibrate_proba=calibrate_proba)

        elif (method == 'overall') and (classifier_info['classifier'] not in core_classifiers):

            clf = prediction_models[classifier_info['classifier']]

            grid_search = GridSearchCV(clf,
                                       param_grid=parameters,
                                       n_jobs=classifier_info['n_jobs'],
                                       cv=k_folds,
                                       verbose=1)

            grid_search.fit(self.p_vars, self.labels)

            logger.info(grid_search.best_estimator_)
            logger.info('  Best score: {:f}'.format(grid_search.best_score_))
            logger.info('  Best parameters: {}'.format(grid_search.best_params_))

        else:

            logger.error('  The score method {} is not supported.'.format(method))
            raise NameError

    def cross_validation(self, X, y, n_splits=5, test_size=0.7, train_size=0.3, random_state=None, **kwargs):

        """
        A cross validation function to replace scikit-learn,
        which does not handle the built-in VotingClassifier

        Example:
            >>> cl = classification()
            >>> cl.split_samples(<args>)
            >>> cl.construct_model(<args>)
            >>>
            >>> cl.cross_validation(n_splits=5, test_size=0.7, train_size=0.3)
            >>> print(cl.cv_scores)
        """

        from sklearn.model_selection import StratifiedShuffleSplit
        from sklearn.metrics import f1_score

        kwargs['input_model'] = None
        kwargs['output_model'] = None

        self.cv_scores = list()

        splitter = StratifiedShuffleSplit(n_splits=n_splits,
                                          test_size=test_size,
                                          train_size=train_size,
                                          random_state=random_state)

        for train_index, test_index in splitter.split(X, y):

            # Set training data
            self.p_vars = X[train_index]
            self.labels = y[train_index]

            # Set test data
            p_vars_test = X[test_index]
            labels_test = y[test_index]

            self.construct_model(**kwargs)

            labels_predict = self.model.predict(p_vars_test)

            score = f1_score(labels_test,
                             labels_predict,
                             average='weighted')

            self.cv_scores.append(score)

    def stack_majority(self, img, output_model, out_img, classifier_info, scale_data=False, ignore_feas=[]):

        """
        A majority vote filter.

        Args:
            img (str): The input image.
            output_model (str): The output model.
            out_img (str): The output map.
            classifier_info (dict): The model parameters dictionary.
            scale_data (Optional[bool or str]): Whether to scale the data prior to classification. 
                Default is False. *If ``scale_data`` is a string, the scaler will be loaded from the string text file.
            ignore_features (Optional[int list]): A list of features to ignore. Default is [].

        Returns:
            None, writes results to ``out_img``.

        Examples:
            >>> import mpglue as gl
            >>>
            >>> cl = gl.classification()
            >>>
            >>> cl.split_samples('/samples.txt', scale_data=True)
            >>>
            >>> # setup three classifiers
            >>> classifier_info = {'classifiers': ['rf', 'SVM', 'bayes'], 'trees': 100, 'C': 1}
            >>> cl.stack_majority('/in_image.tif', '/out_model.xml', '/out_image.tif',
            >>>                   classifier_info, scale_data=True)
            >>>
            >>> # Command line
            >>> > ./classification.py -s /samples.txt -i /in_image.tif -mo /out_model.xml -o /out_image.tif --parameters ...
            >>>     classifiers:RF-SVM-Bayes,trees:100,C:1 --scale yes
        """

        d_name_mdl, f_name_mdl = os.path.split(output_model)
        f_base_mdl, f_ext_mdl = os.path.splitext(f_name_mdl)

        d_name, f_name = os.path.split(out_img)
        f_base, f_ext = os.path.splitext(f_name)

        map_list = []

        for classifier in classifier_info['classifiers']:

            output_model = '%s/%s_%s%s' % (d_name_mdl, f_base_mdl, classifier, f_ext_mdl)

            out_image_temp = '%s/%s_%s%s' % (d_name, f_base, classifier, f_ext)
            map_list.append(out_image_temp)

            classifier_info['classifier'] = classifier

            self.construct_model(output_model=output_model, classifier_info=classifier_info)

            # load the model for multiproccessing
            self.construct_model(input_model=output_model, classifier_info=classifier_info)

            self.predict(img, out_image_temp, scale_data=scale_data, ignore_feas=ignore_feas)

        with raster_tools.ropen(map_list[0]) as i_info:

            rows, cols = i_info.rows, i_info.cols

            i_info.bands = 1

            with raster_tools.create_raster(out_img, i_info, bigtiff='yes') as out_rst:

                out_rst.get_band(1)

                rst_objs = [raster_tools.ropen(img).datasource.GetRasterBand(1) for img in map_list]

                if rows >= 512:
                    blk_size_rows = 512
                else:
                    blk_size_rows = copy(rows)

                if cols >= 1024:
                    block_size_cls = 1024
                else:
                    block_size_cls = copy(cols)

                for i in range(0, rows, blk_size_rows):

                    n_rows = self._num_rows_cols(i, blk_size_rows, rows)

                    for j in range(0, cols, block_size_cls):

                        n_cols = self._num_rows_cols(j, block_size_cls, cols)

                        mode_img = np.vstack(([obj.ReadAsArray(j, i, n_cols, n_rows)
                                               for obj in rst_objs])).reshape(len(map_list), n_rows, n_cols)

                        out_mode = stats.mode(mode_img)[0]

                        out_rst.write_array(out_mode, i=i, j=j)

                for rst_obj in rst_objs:
                    rst_obj.close()
                    rst_obj = None

            out_rst = None

        i_info = None


def importr_tryhard(packname):

    from rpy2.robjects.packages import importr
    utils = importr('utils')

    try:
        __ = importr(packname)
    except:
        utils.install_packages(StrVector(packname))


class classification_r(classification):

    """
    Class interface to R C5/Cubist

    Examples:
        >>> from mpglue.classifiers import classification_r
        >>>
        >>> cl = classification_r()
        >>>
        >>> # load the samples
        >>> # *Note that the sample instances are stored in cl.classification, 
        >>> # structurally different than using the base
        >>> # classification() which inherits the properties directly
        >>> cl.split_samples('/samples.txt', classes2remove=[4, 9],
        >>>                  class_subs={2:.9, 5:.1, 8:.9})
        >>>
        >>> # Train a Cubist model.
        >>> cl.construct_r_model(output_model='/models/cubist_model', classifier_info={'classifier': 'cubist',
        >>>                        'committees': 5, 'rules': 100, 'extrap': 10})
        >>>
        >>> # Predict labels with the Cubist model.
        >>> cl.predict('/feas/image_feas.vrt', '/maps/out_labels.tif',
        >>>            input_model='/models/cubist_model', in_samps='/samples.txt')
        >>>
        >>> # Train a C5 model.
        >>> cl.construct_r_model(output_model='/models/c5_model', classifier_info={'classifier': 'c5',
        >>>                        'trials': 10, 'c5': .25, 'min': 2})
        >>>
        >>> # Predict labels with the C5 model. There is no need
        >>> #   to load a model if the prediction is applied within
        >>> #   the same session.
        >>> cl.predict('/feas/image_feas.vrt', '/maps/out_labels.tif')
        >>>
        >>> # However, you must provide the model
        >>> #   file to predict in parallel.
        >>> # First, load the model
        >>> cl.construct_r_model(input_model='/models/c5_model.tree')
        >>>
        >>> # Then apply the predictions.
        >>> cl.predict('/feas/image_feas.vrt', '/maps/out_labels.tif')
    """

    global R_installed, ro, Cubist, C50, pandas2ri, StrVector

    # rpy2
    try:
        import rpy2.robjects as ro
        from rpy2.robjects.packages import importr

        from rpy2.robjects.numpy2ri import numpy2ri
        ro.numpy2ri.activate()

        # R vector of strings
        from rpy2.robjects.vectors import StrVector

        from rpy2.robjects import pandas2ri
        pandas2ri.activate()

        # import R's utility package
        utils = importr('utils')

        R_installed = True

    except:
        R_installed = False

    if R_installed:

        try:

            # select a mirror for R packages
            utils.chooseCRANmirror(ind=1)  # select the first mirror in the list

            # R package names
            package_names = ('cubist', 'C50', 'raster', 'rgdal')#, 'foreach', 'doSNOW')

            # Selectively install what needs to be install.
            # We are fancy, just because we can.
            # names_to_install = [x for x in package_names if not isinstalled(x)]
            [importr_tryhard(px) for px in package_names]

            # Install necessary libraries.
            # if len(names_to_install) > 0:
            #
            #     print('Installing R packages--{} ...'.format(', '.join(names_to_install)))
            #
            #     utils.install_packages(StrVector(names_to_install))

            # print('Importing R packages--{} ...'.format(', '.join(package_names)))

            # Cubist
            Cubist = importr('cubist', suppress_messages=True)

            # C50
            C50 = importr('C50', suppress_messages=True)

            # raster
            raster = importr('raster', suppress_messages=True)

            # rgdal
            rgdal = importr('rgdal', suppress_messages=True)

            # # foreach
            # foreach = importr('foreach', suppress_messages=True)
            #
            # # doSNOW
            # doSNOW = importr('doSNOW', suppress_messages=True)

        except:
            R_installed = False

    def __init__(self):

        self.time_stamp = time.asctime(time.localtime(time.time()))

        self.OS_SYSTEM = platform.system()

    def construct_r_model(self, input_model=None, output_model=None, write_summary=False,
                          get_probs=False, cost_array=None, case_weights=None,
                          classifier_info={'classifier': 'cubist'}):

        """
        Trains a Cubist model.

        Args:
            input_model (Optional[str]): The input model to load. Default is None.
            output_model (Optional[str]): The output model to write to file. Default is None.
                *No extension should be added. This is added automatically.
            write_summary (Optional[bool]): Whether to write the model summary to file. Default is False.
            get_probs (Optional[bool]): Whether to return class probabilities. Default is False.
            cost_array (Optional[2d array]): A cost matrix, where rows are the predicted costs and columns are
                the true costs. Default is None.

                In the example below, the cost of predicting R as G is 3x more costly as the reverse, predicting
                    R as B ix 7x more costly as the reverse, predicting G as R is 2x more costly as the reverse,
                    and so on.

                        R  G  B
                    R [[0, 2, 4],
                    G  [3, 0, 5],
                    B  [7, 1, 0]]

            case_weights (Optional[list or 1d array]): A list of case weights. Default is None.
            classifier_info (dict): The model parameter dictionary: Default is {'classifier': 'cubist', 
                'committees': 5, 'rules': 100, 'extrap': 10})
        """

        if not R_installed:

            logger.warning('  R and rpy2 must be installed to use C5 or Cubist.')
            return

        self.get_probs = get_probs

        # replace forward slashes for Windows
        if self.OS_SYSTEM == 'Windows':
            output_model = output_model.replace('\\', '/')

        if isinstance(input_model, str):
            self.classifier_info, self.model, self.headers = self.load(input_model)

            self.input_model = input_model
            return

        else:
            self.classifier_info = classifier_info

        # Check if model parameters are set
        #   otherwise, set defaults.
        if self.classifier_info['classifier'] == 'cubist':

            # The number of committees.
            if 'committees' not in self.classifier_info:
                self.classifier_info['committees'] = 5

            # The number of rules.
            if 'rules' not in self.classifier_info:
                self.classifier_info['rules'] = 100

            # Whether to use unbiased rules.
            if 'unbiased' not in self.classifier_info:
                self.classifier_info['unbiased'] = False

            # The extrapolation percentage, between 0-100.
            if 'extrapolation' not in self.classifier_info:
                self.classifier_info['extrapolation'] = 10

        elif self.classifier_info['classifier'] == 'c5':

            # The number of boosted trials.
            if 'trials' not in self.classifier_info:
                self.classifier_info['trials'] = 10

            # The minimum number of cases and node level.
            if 'min_cases' not in self.classifier_info:
                self.classifier_info['min_cases'] = 2

            # Whether to apply winnowing (i.e., feature selection)
            if 'winnow' not in self.classifier_info:
                self.classifier_info['winnow'] = False

            # Whether to turn off global pruning
            if 'no_prune' not in self.classifier_info:
                self.classifier_info['no_prune'] = False

            # The confidence factor for pruning. Low values result
            #   in more pruning.]
            if 'CF' not in self.classifier_info:
                self.classifier_info['CF'] = .25

            # Whether to apply a fuzzy threshold of probabilities.
            if 'fuzzy' not in self.classifier_info:
                self.classifier_info['fuzzy'] = False

        else:

            logger.error('  The classifier must be C5 or Cubist.')
            raise NameError

        if isinstance(output_model, str):

            self.model_dir, self.model_base = os.path.split(output_model)
            self.output_model = '{}/{}.tree'.format(self.model_dir, self.model_base)

            if os.path.isfile(self.output_model):
                os.remove(self.output_model)

            if not os.path.isdir(self.model_dir):
                os.makedirs(self.model_dir)

            os.chdir(self.model_dir)

        ## prepare the predictive samples and labels
        # R('samps = read.csv(file="%s", head=TRUE, sep=",")' % file_name)
        # samps = R['read.csv'](file_name)

        # samps = com.convert_to_r_dataframe(pd.DataFrame(self.p_vars))
        # samps = pandas2ri.py2ri(pd.DataFrame(self.p_vars))
        # samps.colnames = self.headers[:-1]

        samps = ro.r.matrix(self.p_vars, nrow=self.n_samps, ncol=self.n_feas)
        samps.colnames = StrVector(self.headers[:-1])

        if 'cubist' in self.classifier_info['classifier']:
            labels = ro.FloatVector(self.labels)
        elif 'c5' in self.classifier_info['classifier']:
            labels = ro.FactorVector(pd.Categorical(self.labels))

        if isinstance(case_weights, list) or isinstance(case_weights, np.ndarray):
            case_weights = ro.FloatVector(case_weights)

        if isinstance(cost_array, np.ndarray):

            cost_array = ro.r.matrix(cost_array, nrow=cost_array.shape[0], ncol=cost_array.shape[1])
            cost_array.rownames = StrVector(sorted(self.classes))
            cost_array.colnames = StrVector(sorted(self.classes))

        # samps = DataFrame.from_csvfile(self.file_name, header=True, sep=',')
        # R('labels = samps[,c("%s")]' % self.classification.hdrs[-1])
        # labels = samps.rx(True, ro.StrVector(tuple(self.headers[-1:])))
        # R('samps = samps[,1:%d+2]' % self.classification.n_feas)
        # samps = samps.rx(True, ro.IntVector(tuple(range(3, self.n_feas+3))))

        # Train a Cubist model.
        if 'cubist' in self.classifier_info['classifier']:

            logger.info('  Training a Cubist model with {:d} committees, {:d} rules, {:d}% extrapolation, and {:,d} samples ...'.format(self.classifier_info['committees'],
                                                                                                                                        self.classifier_info['rules'],
                                                                                                                                        self.classifier_info['extrapolation'],
                                                                                                                                        self.n_samps))

            # train the Cubist model
            # R('model = Cubist::cubist(x=samps, y=labels, committees=%d, control=cubistControl(rules=%d, extrapolation=%d))' % \
            #   (self.classifier_info['committees'], self.classifier_info['rules'], self.classifier_info['extrap']))

            self.model = Cubist.cubist(x=samps, y=labels, committees=self.classifier_info['committees'],
                                       control=Cubist.cubistControl(rules=self.classifier_info['rules'],
                                                                    extrapolation=self.classifier_info['extrapolation'],
                                                                    unbiased=self.classifier_info['unbiased']))

            if isinstance(output_model, str):

                logger.info('  Writing the model to file ...')

                # Write the Cubist model and .names to file.
                if self.OS_SYSTEM == 'Windows':

                    # R('Cubist::exportCubistFiles(model, prefix="%s")' % self.model_base)
                    Cubist.exportCubistFiles(self.model, prefix=self.model_base)

                else:

                    self.dump([self.classifier_info,
                               self.model,
                               self.headers],
                              self.output_model)

                if write_summary:

                    logger.info('  Writing the model summary to file ...')

                    # Write the Cubist model summary to file.
                    with open(os.path.join(self.model_dir, '{}_summary.txt'.format(self.model_base)), 'wb') as out_tree:
                        out_tree.write(str(Cubist.print_summary_cubist(self.model)))

        elif 'c5' in self.classifier_info['classifier']:

            logger.info('  Training a C5 model with {:d} trials, {:.2f} CF, {:d} minimum cases, and {:,d} samples ...'.format(self.classifier_info['trials'],
                                                                                                                              self.classifier_info['CF'],
                                                                                                                              self.classifier_info['min_cases'],
                                                                                                                              self.n_samps))

            # train the C5 model
            # R('model = C50::C5.0(x=samps, y=factor(labels), trials=%d, control=C5.0Control(CF=%f, minCases=%d))' % \
            #   (self.classifier_info['trials'], self.classifier_info['CF'], self.classifier_info['min']))

            # weights = case_weights,
            # costs = cost_array,

            self.model = C50.C5_0(x=samps, y=labels,
                                  trials=self.classifier_info['trials'],
                                  control=C50.C5_0Control(CF=self.classifier_info['CF'],
                                                          minCases=self.classifier_info['min_cases'],
                                                          winnow=self.classifier_info['winnow'],
                                                          noGlobalPruning=self.classifier_info['no_prune'],
                                                          fuzzyThreshold=self.classifier_info['fuzzy'],
                                                          label='response'))

            if isinstance(output_model, str):

                logger.info('  Writing the model to file ...')

                # Write the C5 tree to file.
                if self.OS_SYSTEM == 'Windows':

                    with open(self.output_model, 'wb') as out_tree:

                        ro.globalenv['model'] = self.model
                        out_tree.write(str(ro.r('model$tree')))

                else:

                    self.dump([self.classifier_info,
                               self.model,
                               self.headers],
                              self.output_model)

                if write_summary:

                    logger.info('  Writing the model summary to file (this may take a few minutes with large trees) ...')

                    # Write the C5 model summary to file.
                    with open(os.path.join(self.model_dir, '{}_summary.txt'.format(self.model_base)), 'wb') as out_imp:
                        out_imp.write(str(C50.print_summary_C5_0(self.model)))

    def predict_c5_cubist(self, input_image, out_image, input_model=None, in_samps=None,
                          ignore_feas=[], row_block_size=1024, col_block_size=1024,
                          mask_background=None, background_band=0, background_value=0,
                          minimum_observations=0, observation_band=0, n_jobs=-1, chunk_size=1024):

        """
        Predicts class labels from C5 or Cubist model.

        Args:
            input_image (str): The image features with the same number of layers as used to train the model.
            out_image (str): The output image.
            input_model (Optional[str]): The full directory and base name of the model to use.
            in_samps (Optional[str]): The image samples used to build the model.
                *This is necessary to match the header names with Windows.
            tree_model (str): The decision tree model to use. Default is 'cubist'. Choices are ['c5' or 'cubist'].
        """

        global predict_samps

        self.ignore_feas = ignore_feas
        self.row_block_size = row_block_size
        self.col_block_size = col_block_size
        self.mask_background = mask_background
        self.background_band = background_band
        self.background_value = background_value
        self.minimum_observations = minimum_observations
        self.observation_band = observation_band
        self.out_image = out_image
        self.n_jobs = n_jobs
        self.chunk_size = chunk_size

        # Block record keeping.
        d_name, f_name = os.path.split(self.out_image)
        f_base, f_ext = os.path.splitext(f_name)

        self.out_image_temp = os.path.join(d_name, '{}_temp.tif'.format(f_base))
        self.record_keeping = os.path.join(d_name, '{}_record.txt'.format(f_base))

        if os.path.isfile(self.record_keeping):
            self.record_list = self.load(self.record_keeping)
        else:
            self.record_list = list()

        if isinstance(input_model, str):
            self.classifier_info, self.model, self.headers = self.load(input_model)

        if self.OS_SYSTEM == 'Windows':

            # input_model = input_model.replace('\\', '/')
            # in_samps = in_samps.replace('\\', '/')
            # input_image = input_image.replace('\\', '/')
            # out_image = out_image.replace('\\', '/')

            out_image_dir, f_name = os.path.split(out_image)
            out_image_base, f_ext = os.path.splitext(f_name)

            if not os.path.isdir(out_image_dir):
                os.makedirs(out_image_dir)

            if 'img' in f_ext.lower():
                out_type = 'HFA'
            elif 'tif' in f_ext.lower():
                out_type = 'GTiff'
            else:
                sys.exit('\nERROR!! The file extension is not supported.\n')

            self.model_dir, self.model_base = os.path.split(input_model)

            self.input_image = input_image

            # get the number of features
            self.i_info = raster_tools.ropen(input_image)

            self.n_feas = self.i_info.bands

            # build the icases file
            self._build_icases(in_samps, tree_model)

            if 'c5' in tree_model:

                # write the .names and .data files to text
                self._build_C5_names(in_samps)

            # self.mapC5_dir = os.path.realpath('../helpers/mapC5')
            # python_home = 'C:/Python27/ArcGIS10.1/Lib/site-packages'
            self.mapC5_dir = os.path.join(MPPATH, 'helpers/mapC5')

            # copy the mapC5 files to the model directory
            self._copy_mapC5(tree_model)

            # change to the map_C5 model directory
            os.chdir(self.model_dir)

            # execute mapC5
            if tree_model == 'cubist':

                com = os.path.join(self.model_dir, 'mapCubist_v202.exe {} {} {}\{}'.format(self.model_base,
                                                                                           out_type,
                                                                                           out_image_dir,
                                                                                           out_image_base))

            elif tree_model == 'c5':

                com = os.path.join(self.model_dir, 'mapC5_v202.exe {} {} {}\{} {}\{}_error'.format(self.model_base,
                                                                                                   out_type,
                                                                                                   out_image_dir,
                                                                                                   out_image_base,
                                                                                                   out_image_dir,
                                                                                                   out_image_base))

            subprocess.call(com, shell=True)

            self._clean_mapC5(tree_model)

        else:

            # Open the image.
            self.i_info = raster_tools.ropen(input_image)

            if self.ignore_feas:
                bands2open = sorted([bd for bd in range(1, self.i_info.bands + 1) if bd not in self.ignore_feas])
            else:
                bands2open = list(range(1, self.i_info.bands + 1))

            # Output image information.
            self.o_info = self.i_info.copy()

            # Set the number of output bands.
            self.o_info.bands = 1

            if self.classifier_info['classifier'] == 'cubist':
                self.o_info.storage = 'float32'
            else:
                self.o_info.storage = 'byte'

            self.o_info.close()

            # Create the output image
            if isinstance(self.mask_background, str):
                out_raster_object = raster_tools.create_raster(self.out_image_temp, self.o_info,
                                                               compress='none', tile=False, bigtiff='yes')
            else:
                out_raster_object = raster_tools.create_raster(self.out_image, self.o_info, tile=False)

            out_raster_object.get_band(1)
            out_raster_object.fill(0)

            rows = self.i_info.rows
            cols = self.i_info.cols

            block_rows, block_cols = raster_tools.block_dimensions(rows, cols,
                                                                   row_block_size=self.row_block_size,
                                                                   col_block_size=self.col_block_size)

            n_blocks = 0
            for i in range(0, rows, block_rows):
                for j in range(0, cols, block_cols):
                    n_blocks += 1

            n_block = 1

            logger.info('  Mapping labels ...')

            for i in range(0, rows, block_rows):

                n_rows = self._num_rows_cols(i, block_rows, rows)

                for j in range(0, cols, block_cols):

                    logger.info('  Block {:,d} of {:,d} ...'.format(n_block, n_blocks))
                    n_block += 1

                    if n_block in self.record_list:

                        logger.info('  Skipping current block ...')
                        continue

                    n_cols = self._num_rows_cols(j, block_cols, cols)

                    features = raster_tools.read(image2open=input_image,
                                                 bands2open=bands2open,
                                                 i=i, j=j,
                                                 rows=n_rows, cols=n_cols,
                                                 predictions=True,
                                                 d_type='float32',
                                                 n_jobs=-1)

                    # Load
                    predict_samps = pandas2ri.py2ri(pd.DataFrame(features))
                    predict_samps.colnames = self.headers

                    # Make the predictions and convert to
                    #   a Pandas Categorical object, followed
                    #   by a conversion to a NumPy array.

                    # Get chunks for parallel processing.
                    samp_rows = predict_samps.shape[0]
                    indice_pairs = []
                    for i_ in range(0, samp_rows, self.chunk_size):
                        n_rows_ = self._num_rows_cols(i_, self.chunk_size, samp_rows)
                        indice_pairs.append([i_, n_rows_])

                    if isinstance(self.input_model, str):

                        predicted = joblib.Parallel(n_jobs=self.n_jobs,
                                             max_nbytes=None)(joblib.delayed(self.c5_predict_parallel)(input_model, ip)
                                                              for ip in indice_pairs)

                        # Write the predictions to file.
                        out_raster_object.write_array(np.array(list(itertools.chain.from_iterable(predicted))).reshape(n_cols, n_rows).T, i, j)

                    else:

                        # Write the predictions to file.
                        out_raster_object.write_array(np.uint8(pandas2ri.ri2py(C50.predict_C5_0(self.model,
                                                                                                newdata=predict_samps))).reshape(n_cols, n_rows).T, i, j)

                    self.record_list.append(n_block)

            out_raster_object.close_all()

            out_raster_object = None

            if isinstance(self.mask_background, str):

                self._mask_background(self.out_image_temp, self.out_image, self.mask_background,
                                      self.background_band, self.background_value, self.minimum_observations,
                                      self.observation_band)

            # ro.r('x = new("GDALReadOnlyDataset", "{}")'.format(input_image))

            # TODO: R predict functionality
            # print(R('names(samps)'))

            # R('x = new("GDALReadOnlyDataset", "%s")' % input_image)
            # R('feas = data.frame(getRasterTable(x))')
            # R('names(feas) = c("x", "y", names(samps))')
            # R('feas = feas[1:%d+2]' % n_feas)
            # R('feas = stack("%s")' % input_image)
            # R('predict(feas, model, filename="%s", format="GTiff", datetype="INT1U", progress="window", package="raster")' % out_img)

            # print(R('names(feas)'))

            # R('predict(feas, fit, filename="%s", format="GTiff", datetype="INT1U", progress="window")' % out_img)

    # def c5_predict_parallel(self, input_model, ip):
    #
    #     ci, m, h = pickle.load(file(input_model, 'rb'))
    #
    #     return np.uint8(pandas2ri.ri2py(C50.predict_C5_0(m, newdata=predict_samps[ip[0]:ip[0]+ip[1]])))

    def _build_icases(self, in_samps, tree_model):

        """
        Creates the icases file needed to run mapC5

        Args:
            in_samps (str): The samples used to train the model.
            tree_model (str): 'c5' or 'cubist'
        """

        icases_txt = os.path.join(self.model_dir, '{}.icases'.format(self.model_base))

        # the output icases file
        if os.path.isfile(icases_txt):
            os.remove(icases_txt)

        icases = open(icases_txt, 'w')

        if 'cubist' in tree_model:
            icases.write('{} ignore 1\n'.format(self.headers[-1]))
        elif 'c5' in tree_model:
            icases.write('X ignore 1\n')
            icases.write('Y ignore 1\n')

        bd = 1
        for hdr in self.headers[2:-1]:

            icases.write('{} {} {:d}\n'.format(hdr, self.input_image, bd))

            bd += 1

        icases.close()

    def _build_C5_names(self, in_samps):

        """
        Builds the C5 .names file.

        Args:
            in_samps (str): The samples used to train the model.
        """

        names_txt = os.path.join(self.model_dir, '{}.names'.format(self.model_base))
        data_txt = os.path.join(self.model_dir, '{}.data'.format(self.model_base))

        # the output .names file
        if os.path.isfile(names_txt):
            os.remove(names_txt)

        if os.path.isfile(data_txt):
            os.remove(data_txt)

        # create the .data file
        shutil.copy2(in_samps, data_txt)

        names = open(names_txt, 'w')

        names.write('{}.\n\n'.format(self.headers[-1]))
        names.write('X: ignore.\n')
        names.write('Y: ignore.\n')

        for hdr in self.headers[2:-1]:

            names.write('{}: continuous.\n'.format(hdr))

        # write the classes
        class_str_list = ','.join(list(map(str, sorted(self.classes))))
        names.write('{}: {}'.format(self.headers[-1], class_str_list))

        names.close()

    def _copy_mapC5(self, tree_model):

        """
        Copies files needed to run mapC5.

        Args:
            tree_model (str): The decision tree model to use ('c5' or 'cubist').
        """

        if tree_model == 'cubist':

            mapC5_list = ['gdal13.dll', 'gdal15.dll', 'install.bat', 'mapCubist_v202.exe', 'msvcp71.dll', 'msvcr71.dll']

        elif tree_model == 'c5':

            mapC5_list = ['gdal13.dll', 'gdal15.dll', 'install.bat', 'mapC5_v202.exe', 'msvcp71.dll', 'msvcr71.dll']

        for mapC5_item in mapC5_list:

            full_item = os.path.join(self.mapC5_dir, mapC5_item)
            out_item = os.path.join(self.model_dir, mapC5_item)

            if not os.path.isfile(out_item):
                shutil.copy2(full_item, out_item)

    def _clean_mapC5(self, tree_model):

        """
        Cleans the C5 directories
        """

        if tree_model == 'cubist':

            mapC5_list = ['gdal13.dll', 'gdal15.dll', 'install.bat', 'mapCubist_v202.exe', 'msvcp71.dll', 'msvcr71.dll']

        elif tree_model == 'c5':

            mapC5_list = ['gdal13.dll', 'gdal15.dll', 'install.bat', 'mapC5_v202.exe', 'msvcp71.dll', 'msvcr71.dll']

        for mapC5_item in mapC5_list:

            full_item = os.path.join(self.model_dir, mapC5_item)

            if os.path.isfile(full_item):
                os.remove(full_item)


def _examples():

    sys.exit("""\

    --Find the optimum RF maximum depth--
    classification.py -s /samples.txt -p .5 --optimize 10
    ... would train and test (50/50) a range of depths over 10 folds cross-validation

    ===============
    Training models
    ===============

    --Train & save a Random Forest model--
    classification.py -s /samples.txt -mo /model_rf.xml
    ... would train and save a Random Forest model to model_rf.xml

    --Train & save a Random Forest model--
    classification.py -s /samples.txt --parameters classifier:RF,trees:2000 -mo /model_rf.xml
    ... would train and save a Random Forest model with 2000 trees to model_rf.xml

    --Train & save a Random Forest model--
    classification.py -s /samples.txt --parameters classifier:RF,trees:2000 -ig 5,10,15 -mo /model_rf.xml
    ... would train and save a Random Forest model with 2000 trees to model_rf.xml. The 5th, 10th, and 15th feature would
    not be used in the model

    --Train & save a Gradient Boosted Tree model--
    classification.py -s /samples.txt -labst float --parameters classifier:Boost -mo /model_boost.xml
    ... would train and save a Gradient Boosted Tree model with 1000 trees to model_boost.xml

    --Train & save a Support Vector Machine model--
    classification.py -s /samples.txt --parameters classifier:SVMA -mo /model_svm.xml --scale yes
    ... would train and save an auto-tuned Support Vector Machine model to model_svm.xml

    --Train & save a Cubist regression model--
    classification.py -s /samples.txt --parameters classifier:Cubist,committees:10,extrap:20 -mo /models/Cubist
    ... would train and save a Cubist model

    --Train & save a C5 model--
    classification.py -s /samples.txt --parameters classifier:C5,trials:10,CF:.4 -mo /models/C5
    ... would train and save a C5 model

    =======
    Mapping
    =======

    --Load model & map image--
    classification.py -mi /model_rf.xml -i /image_feas.tif -o /mapped_image.tif
    ... would load a Random Forest model and map image image_feas.tif

    --Load model & map image--
    classification.py -mi /model_rf.xml -ig 5,10,15 -i /image_feas.tif -o /mapped_image.tif
    ... would load a Random Forest model and map image image_feas.tif, ignore the 5th, 10th, and 15th image layer during
    the classification process.

    --Load model & map image--
    classification.py -mi /model_rf.xml -i /image_feas.tif -o /mapped_image.tif --rank RF -rankt /ranked_feas.txt --accuracy /accuracy.txt
    ... would load a Random Forest model, map image image_feas.tif, write ranked RF features to text, and write accuracy report to text

    --Load model & map image--
    classification.py -mi /model_Cubist -s /samples.txt --parameters classifier:Cubist -i /image_feas.tif -o /mapped_image.tif
    ... would load a Cubist model model and map image image_feas.tif

    ==================
    Ranking & Accuracy
    ==================

    --Rank and subset features--
    classification.py -s /samples.txt -i /image_feas.tif -or /image_feas_ranked.vrt --rank chi2
    ... would rank image features with Chi^2 and write to image_feas_ranked.vrt

    --Test model accuracy--
    classification.py -s /samples.txt --accuracy /accuracy.txt -mi /model_rf.xml
    ... would test the accuracy of model_rf.xml on 10% of data randomly sampled

    --Test model accuracy--
    classification.py -s /samples.txt --accuracy /accuracy.txt -mi /model_rf.xml -p .5
    ... would test the accuracy of model_rf.xml on 50% of data randomly sampled

    --Test model accuracy--
    classification.py -s /samples.txt --accuracy /accuracy.txt
    ... would test the accuracy of a new RF model on 10% of data withheld from training
    """)


def _usage():

    sys.exit("""\

    classification.py ...

    PRE-PROCESSING
    ==============
        [-s <Training samples (str) :: Default=None>]
        [-labst <Labels type (int or float) (str) :: Default=int>]
            *For reading samples (-s)
        [-p <Percent to sample from all samples (float) :: Default=.9>]
        [-pe <Percent to sample from each class (float) :: Default=None>]
            *Overrides -p
        [--subs <Dictionary of samples per class (dict) in place of -p :: Default={}>]
        [--recode <Dictionary recoded class values (dict) :: Default={}>]
        [-clrm <Classes to remove from data (int list) :: Default=[]>]
        [-valrm <Values, based on feature, to remove from data (val,fea) :: Default=[]>]
        [-ig <Features to ignore (int list) :: Default=[]>]
        [-xy <Use x, y coordinates as predictive variables? :: Default=no>]
        [--outliers <Remove outliers (str) :: Default=no>]
        [--loc_outliers <Locate outliers and do not remove (str) :: Default=no>]
        [--scale <Scale data (str) :: Default=no>]
        [--semi <Semi supervised labeling (str) :: Default=no>]
        [--visualize <Visualize data in feature space on two or three features (fea1,fea2,OPTfea3) :: Default=[]>]
        [--decision <Visualize the decision function on two features (fea1,fea2,class,compare--1 or 2) :: Default=[]>]
    MODEL
    =====
        [--parameters <Classifier & parameters (str) :: Default=classifier:RF>]
            *Use --parameters key1:parameter,key2:parameter except with --majority, where classifiers:RF-SVM-EX_RF-Bayes, e.g.
        [-mi <Input model (str) :: Default=None>]
        [-mo <Output model (str), .txt for Scikit models, .xml for OpenCV models :: Default=None>]
        [--accuracy <Accuracy of test samples withheld from training (str) :: Default=Automatic with -mo>]
        [-probs <Get class probability layers instead of labels (str) :: Default=no>]
        [--rank <Rank method (str) :: Default=None>]
        [-topf <Number of top features to subset (int -total- or float -percentage-) :: Default=1.>]
        [-or <Output ranked image (str) :: Default=None>]
        [-rankt <Write ranked features to rankt text (str) :: Default=None>]
        [--optimize <Optimize parameters (str) :: Default=no>]
    MAPS
    ====
        [--majority <Rank the majority classification with --parameters classifiers:cl1-cl2-cl3-etc (str) :: Default=no>]
        [-i <Input image to classify (str) :: Default=None>]
        [-o <Output classified image (str) :: Default=None>]
        [-addl <Additional images to use in the model (str list) :: Default=[]>]
        [--jobs <Number of jobs for parallel mapping, with --multi (int) :: Default=-1>]
        [-c <Chunk size for parallel mapping (int) :: Default=8000>]
        [-bc <Band to check for zeros (int) :: Default=-1]
    [-h <Prints this dialogue>
    [--options <Print list of classifier options>]
    [-e <Prints examples>

    """)


def main():

    argv = sys.argv

    if argv is None:
        sys.exit(0)

    samples = None
    img = None
    out_img = None
    out_img_rank = None
    input_model = None
    output_model = None
    perc_samp = 0.9
    perc_samp_each = 0
    scale_data = False
    labs_type = 'int'
    class_subs = dict()
    recode_dict = dict()
    classes2remove = list()
    valrm_fea = list()
    ignore_feas = list()
    use_xy = False
    outrm = False
    locate_outliers = False
    semi = False
    semi_kernel = 'knn'
    feature_space = list()
    decision_function = list()
    header = True
    norm_struct = True
    classifier_info = {'classifier': 'rf'}
    var_imp = True
    rank_method = None
    top_feas = 1.
    out_acc = None
    get_majority = False
    optimize = False
    rank_txt = None
    get_probs = False
    additional_layers = list()
    n_jobs = -1
    band_check = -1
    chunk_size = 8000

    #print("optimize "+ optimize )
    i = 1
    while i < len(argv):

        arg = argv[i]

        if arg == '-i':
            i += 1
            img = argv[i]

        elif arg == '-o':
            i += 1
            out_img = argv[i]

        elif arg == '-or':
            i += 1
            out_img_rank = argv[i]

        elif arg == '-s':
            i += 1
            samples = argv[i]

        elif arg == '--scale':
            i += 1
            scale_data = argv[i]

            if scale_data == 'yes':
                scale_data = True

        elif arg == '--parameters':
            i += 1

            classifier_info = argv[i]
            classifier_info = classifier_info.split(',')

            info_dict = '{'
            cli_ctr = 1
            for cli in classifier_info:

                cli_split = cli.split(':')

                if 'classifiers' in cli:
                    if cli_ctr == len(classifier_info):
                        info_dict = "%s'%s':%s" % (info_dict, cli_split[0], cli_split[1].split('-'))
                    else:
                        info_dict = "%s'%s':%s," % (info_dict, cli_split[0], cli_split[1].split('-'))
                elif cli_ctr == len(classifier_info):
                    info_dict = "%s'%s':'%s'" % (info_dict, cli_split[0], cli_split[1])
                else:
                    info_dict = "%s'%s':'%s'," % (info_dict, cli_split[0], cli_split[1])

                cli_ctr += 1

            info_dict = '%s}' % info_dict

            classifier_info = ast.literal_eval(info_dict)

            # convert values to integers
            for key in classifier_info:
                is_int = False
                try:
                    classifier_info[key] = int(classifier_info[key])
                    is_int = True
                except:
                    pass

                if not is_int:
                    try:
                        classifier_info[key] = float(classifier_info[key])
                    except:
                        pass

        elif arg == '-p':
            i += 1
            perc_samp = float(argv[i])

        elif arg == '-pe':
            i += 1
            perc_samp_each = float(argv[i])

        elif arg == '--subs':
            i += 1

            class_subs = ''.join(argv[i])
            class_subs = '{%s}' % class_subs

            class_subs = ast.literal_eval(class_subs)

        elif arg == '--recode':
            i += 1

            recode_dict = ''.join(argv[i])
            recode_dict = '{%s}' % recode_dict

            recode_dict = ast.literal_eval(recode_dict)

        elif arg == '-clrm':
            i += 1
            classes2remove = argv[i].split(',')
            classes2remove = list(map(int, classes2remove))

        elif arg == '-valrm':
            i += 1
            valrm_fea = argv[i].split(',')
            valrm_fea = list(map(int, valrm_fea))

        elif arg == '-ig':
            i += 1
            ignore_feas = argv[i].split(',')
            ignore_feas = list(map(int, ignore_feas))

        elif arg == '-xy':
            i += 1
            use_xy = argv[i]
            if use_xy == 'yes':
                use_xy = True

        elif arg == '--outliers':
            i += 1
            outrm = argv[i]
            if outrm == 'yes':
                outrm = True

        elif arg == '--loc_outliers':
            i += 1
            locate_outliers = argv[i]
            if locate_outliers == 'yes':
                locate_outliers = True

        elif arg == '--semi':
            i += 1
            semi = argv[i]
            if semi == 'yes':
                semi = True

        elif arg == '-semik':
            i += 1
            semi_kernel = argv[i]

        elif arg == '--visualize':
            i += 1
            feature_space = argv[i].split(',')
            feature_space = list(map(int, feature_space))

        elif arg == '--decision':
            i += 1
            decision_function = argv[i].split(',')
            decision_function = list(map(int, decision_function))

        elif arg == '--optimize':
            i += 1
            if argv[i] == 'yes':
                optimize = True

        elif arg == '-mi':
            i += 1
            input_model = argv[i]

        elif arg == '-mo':
            i += 1
            output_model = argv[i]

        elif arg == '--rank':
            i += 1
            rank_method = argv[i]

        elif arg == '-rankt':
            i += 1
            rank_txt = argv[i]

        elif arg == '-labst':
            i += 1
            labs_type = argv[i]

        elif arg == '-topf':
            i += 1
            top_feas = argv[i]

            if '.' in top_feas:
                top_feas = float(top_feas)
            else:
                top_feas = int(top_feas)

        elif arg == '--accuracy':
            i += 1
            out_acc = argv[i]

        elif arg == '--majority':
            i += 1
            get_majority = argv[i]
            if get_majority == 'yes':
                get_majority = True

        elif arg == '-probs':
            i += 1
            get_probs = argv[i]

            if get_probs == 'yes':
                get_probs = True

        elif arg == '-addl':
            i += 1
            additional_layers = argv[i].split(',')

        elif arg == '--jobs':
            i += 1
            n_jobs = int(argv[i])

        elif arg == '-bc':
            i += 1
            band_check = int(argv[i])

        elif arg == '-c':
            i += 1
            chunk_size = int(argv[i])

        elif arg == '-h':
            _usage()

        elif arg == '-e':
            _examples()

        elif arg == '--options':
            _options()

        elif arg[:1] == ':':
            logger.info('  Unrecognized command option: %s' % arg)
            _usage()

        i += 1

    logger.info('\nStart date & time --- (%s)\n' % time.asctime(time.localtime(time.time())))

    start_time = time.time()

    try:
        dummy = classifier_info['classifier']
    except:
        classifier_info['classifier'] = 'rf'

    if 'cubist' in classifier_info['classifier'] or 'c5' in classifier_info['classifier']:

        # create the C5/Cubist object
        cl = c5_cubist()

        if samples:

            if rank_method:
                scale_data = True

            cl.split_samples(samples, perc_samp=perc_samp, perc_samp_each=perc_samp_each, scale_data=scale_data, \
                           class_subs=class_subs, header=header, norm_struct=norm_struct, labs_type=labs_type, \
                           recode_dict=recode_dict, classes2remove=classes2remove, ignore_feas=ignore_feas)

            if valrm_fea:
                cl.remove_values(valrm_fea[0], valrm_fea[1])

            if outrm:
                cl.remove_outliers(locate_only=locate_outliers)

        # train the model
        if output_model:

            # train the C5/Cubist model
            cl.train_c5_cubist(samples, output_model, classifier_info=classifier_info)

            # cl = classification()

            # cl.split_samples(samples, perc_samp=perc_samp, header=header, norm_struct=norm_struct, labs_type='float')

            # out_acc = '%s/%s_acc.txt' % (c5_cubist.model_dir, c5_cubist.model_base)

            # cl.test_accuracy(out_acc=out_acc, discrete=False)

        # predict labels
        if input_model and out_img:

            cl.map_labels_c5_cubist(input_model, samples, img, out_img, tree_model=classifier_info['classifier'])

    else:
        #print("optimize2 "+ optimize )

        # create the classifier object
        cl = classification()

        # get predictive variables and class labels data
        # DB
        # optimize = True
        # DB

        if optimize:
            #print("optimize True")
            cl.optimize_parameters(samples, classifier_info, perc_samp, max_depth_range=(1, 100), k_folds=optimize)

            # DB
            # cl.optimize_parameters(samples, classifier_info, n_trees_list=[100, 500, 1000], max_depth_list=[25, 50, 100], k_folds=5) 
            # DB

            logger.info('  The optimum depth was %d' % cl.opt_depth)
            logger.info('  The maximum accuracy was %f' % cl.max_acc)

        if samples:

            if rank_method:
                scale_data = True

            cl.split_samples(samples, perc_samp=perc_samp, perc_samp_each=perc_samp_each, scale_data=scale_data, \
                           class_subs=class_subs, header=header, norm_struct=norm_struct, labs_type=labs_type, \
                           recode_dict=recode_dict, classes2remove=classes2remove, ignore_feas=ignore_feas, \
                           use_xy=use_xy)

            if feature_space:

                if len(feature_space) == 3:
                    fea_z = feature_space[2]
                else:
                    fea_z = None

                if semi:
                    # classified_labels = np.where(cl.labels != -1)
                    classified_labels = None
                else:
                    classified_labels = None

                cl.vis_data(feature_space[0], feature_space[1], fea_3=fea_z, labels=classified_labels)

            if valrm_fea:

                cl.remove_values(valrm_fea[0], valrm_fea[1])

            if semi:

                cl.semi_supervised(classifier_info, kernel=semi_kernel)

                if feature_space:

                    if len(feature_space) == 3:
                        fea_z = feature_space[2]
                    else:
                        fea_z = None

                    cl.vis_data(feature_space[0], feature_space[1], fea_3=fea_z, labels=classified_labels)

            if outrm:

                cl.remove_outliers(locate_only=locate_outliers)

                if feature_space:

                    if len(feature_space) == 3:
                        fea_z = feature_space[2]
                    else:
                        fea_z = None

                    cl.vis_data(feature_space[0], feature_space[1], fea_3=fea_z, labels=classified_labels)

            if decision_function:

                cl.vis_decision(decision_function[0], decision_function[1], classifier_info=classifier_info,
                                class2check=decision_function[2], compare=decision_function[3],
                                locate_outliers=locate_outliers)

        if get_majority:

            cl.stack_majority(img, output_model, out_img, classifier_info, scale_data, ignore_feas=ignore_feas)

        if input_model or output_model or img or (rank_method == 'rf') or out_acc and not get_majority and \
                (rank_method != 'chi2'):

            cl.construct_model(input_model=input_model, output_model=output_model, classifier_info=classifier_info,
                               var_imp=var_imp, rank_method=rank_method, top_feas=top_feas, get_probs=get_probs)

            if out_acc:
                cl.test_accuracy(out_acc=out_acc)

        if rank_method:

            cl.rank_feas(rank_text=rank_txt, rank_method=rank_method, top_feas=top_feas)

        if out_img and not get_majority:

            # apply classification model to map image class labels
            cl.predict(img, out_img, additional_layers=additional_layers, n_jobs=n_jobs, band_check=band_check,
                       scale_data=scale_data, ignore_feas=ignore_feas, chunk_size=chunk_size, use_xy=use_xy)

        if out_img_rank:

            cl.sub_feas(img, out_img_rank)

    logger.info('\nEnd data & time -- (%s)\nTotal processing time -- (%.2gs)\n' %
                (time.asctime(time.localtime(time.time())), (time.time()-start_time)))


if __name__ == '__main__':
    main()
