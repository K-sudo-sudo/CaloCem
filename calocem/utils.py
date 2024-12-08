import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.interpolate import UnivariateSpline
from pathlib import Path
import re

def create_base_plot(data, ax, _age_col, _target_col, sample):
    """
    create base plot
    """
    if isinstance(ax, matplotlib.axes._axes.Axes):
        new_ax = False
    else:
        new_ax = True
        _, ax = plt.subplots()

    ax.plot(data[_age_col], data[_target_col], label=Path(sample).stem)

    # check if std deviation is available
    std_present = [s for s in data.columns if "std" in s]
    if std_present:
        #data = data.query("normalized_heat_flow_w_g_std.notnull()", engine="python")
        ax.fill_between(
            data[_age_col],
            data[_target_col] - data[_target_col + "_std"],
            data[_target_col] + data[_target_col + "_std"],
            alpha=0.5,
        )
    return ax, new_ax


def style_base_plot(
    ax, _target_col, _age_col, sample, limits=None, time_discarded_s=None
):
    """
    style base plot
    """
    ax.set_ylabel(_target_col)
    ax.set_xlabel(_age_col)
    ax.set_title(f"Sample: {Path(sample).stem}")
    if time_discarded_s is not None:
        print("time_discarded_s", time_discarded_s)
        ax.fill_between(
            [ax.get_ylim()[0], time_discarded_s],
            [ax.get_ylim()[0]] ,
            [ax.get_ylim()[1]] ,
            color="black",
            alpha=0.35,
        )
    if limits is not None:
        ax.set_xlim(limits["left"], limits["right"])
        ax.set_ylim(limits["bottom"], limits["top"])
   # ax.set_ylim(0, plt_top)
    ax.legend()
    return ax

def get_data_limits(data, _age_col, _target_col):
    """
    get data limits
    """
    limits = {
        "left": data[_age_col].min(),
        "right": data[_age_col].max(),
        "bottom": data[_target_col].min(),
        "top": data[_target_col].max(),
    }
    return limits

#
# conversion of DataFrame to float
#
def convert_df_to_float(df: pd.DataFrame) -> pd.DataFrame:
    """
    convert

    Parameters
    ----------
    df : TYPE
        DESCRIPTION.

    Returns
    -------
    None.

    """

    # type conversion
    for c in df.columns:
        # safe type conversion of the columns to float if possible
        try:
            df[c] = df[c].astype(float)
        except (ValueError, TypeError):
            pass

    return df


def fit_univariate_spline(df, target_col, s=1e-6):
    """
    fit_univariate_spline

    Parameters
    ----------
    df : pandas dataframe
        DESCRIPTION.

    target_col : str
        DESCRIPTION.

    s : float, optional
        DESCRIPTION. The default is 1e-6.

    """
    df[target_col].fillna(0, inplace=True)
    spl = UnivariateSpline(df["time_s"], df[target_col], s=s)
    df["interpolated"] = spl(df["time_s"])
    # cut off last 100 points to avoid large gradient detection due to potential interpolation artifacts at the end of the data
    df = df.iloc[:-100, :]
    return df


def remove_unnecessary_data(df):
    # cut out data part
    df = df.iloc[1:, :].reset_index(drop=True)

    # drop column
    try:
        data = df.drop(columns=["time_markers_nan"])
    except KeyError:
        pass

    # remove columns with too many NaNs
    data = data.dropna(axis=1, thresh=3)

    # # remove rows with NaNs
    data = data.dropna(axis=1)

    return data


def add_sample_info(df, file):

    # get sample name
    sample_name = Path(file).stem

    # add sample information
    df["sample"] = file
    # df["sample_short"] = sample_name
    df = df.assign(sample_short=sample_name)

    return df

def tidy_colnames(df):
    # get new column names
    new_columnames = []
    for i in df.iloc[0, :]:
        # build
        new_columname = (
            re.sub(r'[\s\n\[\]\(\)° _"]+', "_", i.lower())
            .replace("/", "_")
            .replace("_signal_", "_")
            .strip("_")
        )

        # select appropriate unit
        if new_columname == "time":
            new_columname += "_s"
        elif "temperature" in new_columname:
            new_columname += "_c"
        elif new_columname == "heat_flow":
            new_columname += "_w"
        elif new_columname == "heat":
            new_columname += "_j"
        elif new_columname == "normalized_heat_flow":
            new_columname += "_w_g"
        elif new_columname == "normalized_heat":
            new_columname += "_j_g"
        else:
            new_columname += "_nan"

        # add to list
        new_columnames.append(new_columname)

    # set
    df.columns = new_columnames
    # validate new column names
    if not "time_s" in new_columnames:
        # stop here
        return None

    return df


def parse_rowwise_data(data):

    # get "column" count
    data["count"] = [len(i) for i in data[0].str.split(",")]

    # get most frequent count --> assume this for selection of "data" rows
    data = data.loc[data["count"] == data["count"].value_counts().index[0], [0]]

    # init and loop list of lists
    list_of_lists = []
    for _, r in data.iterrows():
        # append to list
        list_of_lists.append(str(r.to_list()).strip("['']").split(","))

    # get DataFrame from list of lists
    data = pd.DataFrame(list_of_lists)

    return data


def make_equidistant(df: pd.DataFrame) -> pd.DataFrame:
    df = df.reset_index(drop=True)
    df["td"] = pd.to_timedelta(df["time_s"], unit="s")
    resample = df.resample("10s", on="td")
    string_cols = df.select_dtypes(include="object").columns
    num_cols = df.select_dtypes(include="number").columns
    resampled_stringcols = resample[string_cols].first().ffill()
    resampled_numcols = resample[num_cols].mean().interpolate()
    df = pd.concat([resampled_stringcols, resampled_numcols], axis=1)
    return df


def apply_resampling(df: pd.DataFrame, resampling_s="10s") -> pd.DataFrame:
    resampler = df.set_index(pd.to_datetime(df["time_s"], unit="s")).resample(
        resampling_s
    )
    string_cols = df.select_dtypes(include="object").columns
    num_cols = df.select_dtypes(include="number").columns
    resampled_stringcols = resampler[string_cols].first().ffill()
    resampled_numcols = resampler[num_cols].mean().interpolate()
    df = pd.concat([resampled_stringcols, resampled_numcols], axis=1)
    df["time_s"] = (df.index - df.index[0]).total_seconds()
    return df
    df = pd.concat([resampled_stringcols, resampled_numcols], axis=1)
    df["time_s"] = (df.index - df.index[0]).total_seconds()
    return df


def downsample_sections(df, x_col, y_col, processparams):
    """
    Downsample a DataFrame by dividing it into sections and downsampling each section individually.

    Parameters:
    - df: pandas DataFrame with columns 'x' and 'y'.
    - x_col: String for the 'x' values column of the DataFrame.
    - y_col: String for the 'y' values column of the DataFrame.
    - num_points: Desired number of points in the downsampled DataFrame.
    - smoothing_factor: Smoothing factor for the spline interpolation.

    Returns:
    - downsampled_df: Downsampled pandas DataFrame.
    """
    # Time Split
    time_split = processparams.downsample.section_split_time_s #1000

    # Split the DataFrame into sections based on the time column
    df1 = df[df[x_col] < time_split]
    df2 = df[df[x_col] >= time_split]

    # Downsample each section individually
    if not df1.empty:
        downsampled_df1 = adaptive_downsample(
            df1, x_col, y_col, processparams
        )
    if not df2.empty:
        downsampled_df2 = adaptive_downsample(
            df2, x_col, y_col, processparams
        )

    # Concatenate the downsampled sections
    if not df1.empty and not df2.empty:
        downsampled_df = pd.concat([downsampled_df1, downsampled_df2])
    elif not df1.empty:
        downsampled_df = downsampled_df1
    elif not df2.empty:
        downsampled_df = downsampled_df2

    return downsampled_df


def adaptive_downsample(
    df, x_col, y_col, processparams: ProcessingParameters
):
    """
    Adaptively downsample a DataFrame based on the second derivative magnitude.

    Parameters:
    - df: pandas DataFrame with columns 'x' and 'y'.
    - x_col: String for the 'x' values column of the DataFrame.
    - y_col: String for the 'y' values column of the DataFrame.
    - num_points: Desired number of points in the downsampled DataFrame.
    - smoothing_factor: Smoothing factor for the spline interpolation.

    Returns:
    - downsampled_df: Downsampled pandas DataFrame.
    """

    if processparams.downsample.section_split:
        num_points = int(processparams.downsample.num_points / 2)

    #df = df.query("time_s > 1800")
    x = df[x_col].values
    y = df[y_col].values

    # print(y)
    # interpolate the data
    spl = UnivariateSpline(x, y, s=processparams.downsample.smoothing_factor)
    new_x = x  # np.linspace(x.min(), x.max(), len(x))
    # print(new_x)
    new_y = spl(new_x)

    # Compute the first derivative (gradient)
    dy_dx = np.gradient(new_y, new_x)

    # Compute the second derivative
    d2y_dx2 = np.gradient(dy_dx, new_x)

    # Compute the absolute value of the second derivative
    curvature = np.abs(d2y_dx2)
    # Avoid division by zero by adding a small constant
    curvature += 1e-15
    # Normalize curvature
    curvature_normalized = curvature / curvature.sum()

    # Create PDF with a baseline to ensure sampling in low-curvature areas
    baseline_weight = processparams.downsample.baseline_weight
    pdf = curvature_normalized + baseline_weight / num_points
    pdf /= pdf.sum()  # Normalize to create a valid PDF

    # Compute CDF
    cdf = np.cumsum(pdf)

    # plt.plot(x, y)
    # plt.plot(x, new_y, label="interpolated")
    # plt.plot(x, y, label="raw")
    # plt.plot(x, new_y, label="interpolated")
    # plt.plot(x, dy_dx, label="gradient")
    # plt.plot(x, d2y_dx2, label="second derivative")
    # plt.plot(x, curvature, label="curvature")
    # plt.scatter(new_x, pdf, label="pdf")

    # plt.plot(x, cdf, label="cdf")
    # plt.legend()
    # # plt.yscale("log")
    # plt.show()

    # # # Generate uniformly spaced samples in the interval [0, 1)
    uniform_samples = np.linspace(0, 1, num_points, endpoint=False)

    # # # Map uniform samples to indices using the inverse CDF
    indices = np.searchsorted(cdf, uniform_samples)
    # print(indices)
    # # # Ensure indices are within valid range

    indices = np.clip(indices, 0, len(df) - 1)
    # #

    # # Remove duplicates and sort indices
    indices = np.unique(indices)
    # indices = np.argsort(pdf)[-num_points:]
    # print(indices)

    # Subsample the DataFrame at these indices
    downsampled_df = df.iloc[indices]
    # name of sample
    sample_name = df["sample_short"].iloc[0]
    print(f"Downsampled {sample_name} to", len(downsampled_df), "points")
    return downsampled_df

# def calculate_smoothed_heatflow_derivatives(
#     df: pd.DataFrame,
#     tianparams: TianParameters,
#     # window: int = 11,
#     # polynom: int = 3,
#     # spline_smoothing_1st=2e-13,
#     # spline_smoothing_2nd: float = 1e-9,
#     # apply_savgol: bool = True,
# ) -> tuple:
#     """
#     calculate first and second derivative of heat flow

#     Parameters
#     ----------
#     df : pandas DataFrame
#         A dataframe containing the calorimetry data.

#     window : int, optional
#         Window size for Savitzky-Golay filter. The default is 11.

#     polynom : int, optional
#         Polynom order for Savitzky-Golay filter. The default is 3.

#     spline_smoothing : float, optional
#         Smoothing factor for spline interpolation. The default is 1e-9.

#     Returns
#     -------
#     df["first_derivative"] : pandas Series
#         First derivative of the heat flow.

#     df["second_derivative"] : pandas Series
#         Second derivative of the heat flow.

#     """

#     # calculate first derivative
#     if tianparams.savgol["apply"]:
#         df["norm_hf_smoothed"] = non_uniform_savgol(
#             df["time_s"].values,
#             df["normalized_heat_flow_w_g"].values,
#             window=tianparams.savgol["window"],
#             polynom=tianparams.savgol["polynom"],
#         )
#         df["first_derivative"] = np.gradient(df["norm_hf_smoothed"], df["time_s"])
#     else:
#         df["first_derivative"] = np.gradient(df["normalized_heat_flow_w_g"], df["time_s"])

#     df["first_derivative"] = df["first_derivative"].fillna(value=0)

#     if tianparams.median_filter["apply"]:
#         df["first_derivative"] = median_filter(df["first_derivative"], size=7)

#     if tianparams.spline_interpolation["apply"]:
#         f = UnivariateSpline(
#             df["time_s"], df["first_derivative"], k=3, s=tianparams.spline_interpolation["smoothing_1st_deriv"], ext=1
#         )
#         df["first_derivative_smoothed"] = f(df["time_s"])
#     else:
#         df["first_derivative_smoothed"] = df["first_derivative"]

#     # calculate second derivative
#     df["second_derivative"] = np.gradient(df["first_derivative"], df["time_s"])
#     df["second_derivative"] = median_filter(df["second_derivative"], size=7)
#     if tianparams.savgol["apply"]:
#         # interpolate first derivative for better smoothing
#         df["second_derivative"] = non_uniform_savgol(
#             df["time_s"].values,
#             df["second_derivative"].values,
#             window=window,
#             polynom=polynom,
#         )

#     f = UnivariateSpline(
#         df["time_s"], df["second_derivative"], k=3, s=spline_smoothing_2nd, ext=1
#     )
#     df["second_derivative_smoothed"] = f(df["time_s"])

#     return df["first_derivative_smoothed"], df["second_derivative_smoothed"]


# https://dsp.stackexchange.com/questions/1676/savitzky-golay-smoothing-filter-for-not-equally-spaced-data
def non_uniform_savgol(x, y, window, polynom):
    """
    Applies a Savitzky-Golay filter to y with non-uniform spacing
    as defined in x

    This is based on https://dsp.stackexchange.com/questions/1676/savitzky-golay-smoothing-filter-for-not-equally-spaced-data
    The borders are interpolated like scipy.signal.savgol_filter would do

    Parameters
    ----------
    x : array_like
        List of floats representing the x values of the data
    y : array_like
        List of floats representing the y values. Must have same length
        as x
    window : int (odd)
        Window length of datapoints. Must be odd and smaller than x
    polynom : int
        The order of polynom used. Must be smaller than the window size

    Returns
    -------
    np.array of float
        The smoothed y values
    """
    if len(x) != len(y):
        raise ValueError('"x" and "y" must be of the same size')

    if len(x) < window:
        raise ValueError("The data size must be larger than the window size")

    if type(window) is not int:
        raise TypeError('"window" must be an integer')

    if window % 2 == 0:
        raise ValueError('The "window" must be an odd integer')

    if type(polynom) is not int:
        raise TypeError('"polynom" must be an integer')

    if polynom >= window:
        raise ValueError('"polynom" must be less than "window"')

    half_window = window // 2
    polynom += 1

    # Initialize variables
    A = np.empty((window, polynom))  # Matrix
    tA = np.empty((polynom, window))  # Transposed matrix
    t = np.empty(window)  # Local x variables
    y_smoothed = np.full(len(y), np.nan)

    # Start smoothing
    for i in range(half_window, len(x) - half_window, 1):
        # Center a window of x values on x[i]
        for j in range(0, window, 1):
            t[j] = x[i + j - half_window] - x[i]

        # Create the initial matrix A and its transposed form tA
        for j in range(0, window, 1):
            r = 1.0
            for k in range(0, polynom, 1):
                A[j, k] = r
                tA[k, j] = r
                r *= t[j]

        # Multiply the two matrices
        tAA = np.matmul(tA, A)

        # Invert the product of the matrices
        tAA = np.linalg.inv(tAA)

        # Calculate the pseudoinverse of the design matrix
        coeffs = np.matmul(tAA, tA)

        # Calculate c0 which is also the y value for y[i]
        y_smoothed[i] = 0
        for j in range(0, window, 1):
            y_smoothed[i] += coeffs[0, j] * y[i + j - half_window]

        # If at the end or beginning, store all coefficients for the polynom
        if i == half_window:
            first_coeffs = np.zeros(polynom)
            for j in range(0, window, 1):
                for k in range(polynom):
                    first_coeffs[k] += coeffs[k, j] * y[j]
        elif i == len(x) - half_window - 1:
            last_coeffs = np.zeros(polynom)
            for j in range(0, window, 1):
                for k in range(polynom):
                    last_coeffs[k] += coeffs[k, j] * y[len(y) - window + j]

    # Interpolate the result at the left border
    for i in range(0, half_window, 1):
        y_smoothed[i] = 0
        x_i = 1
        for j in range(0, polynom, 1):
            y_smoothed[i] += first_coeffs[j] * x_i
            x_i *= x[i] - x[half_window]

    # Interpolate the result at the right border
    for i in range(len(x) - half_window, len(x), 1):
        y_smoothed[i] = 0
        x_i = 1
        for j in range(0, polynom, 1):
            y_smoothed[i] += last_coeffs[j] * x_i
            x_i *= x[i] - x[-half_window - 1]

    return y_smoothed
