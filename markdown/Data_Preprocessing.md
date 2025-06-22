# Pipe

```r
# 
|>
```

# View Data

Assume that <u>flights</u> is a tibble with 336,776 rows and 19 columns.

```r
# Open an interactive, scrollabl and filterable view
View(flights)
# Columns run down the page, data run across
glimpse(flights)
```

# Data Transformation

Assume that <u>flights</u> is a tibble with 336,776 rows and 19 columns.

## Rows Operators

### fliter

**`fliter()`** keeps rows based on the values of the columns.

```r
flights |>
    fliter(a == 1 & b > 1 | c == 1 | d %in% c(1, 2))
```

### arrange

**`arrange()`** changes the order of the rows based on the values of the columns. If multiple columns are provided, it sorts the rows according to the order of the columns. In case of ties, it uses the subsequent columns to break the tie. 

```r
flights |>
    arrange(year, month, desc(day), dep_time)
```

Use **`desc()`** to sort the rows in descending order (big to small).

### distinct

**`distinct()`** finds all the unique rows or distinct combination of some variables in a tibble. It will <u>find the first occurrence</u> of them and discard the rest. 

```r
# unique rows
flights |>
    distinct(.keep_all = FALSE)
# unique combination of variables
flights |>
    distinct(origin, dest, .keep_all = TRUE)
```

**`.keep_all`** controls whether to keep other columns when filtering for unique rows or unique combinition of variables.

## Columns Operators

### mutate

**`mutate()`** adds new columns that are calculated from the existing columns to the tibble.  

```r
mutate(
  .data,
  ...,
  .by = NULL,
  .keep = c("all", "used", "unused", "none"),
  .before = NULL,
  .after = 
```

1. **`.data`**: A data frame, data frame extension (e.g. a tibble), or a lazy data frame (e.g. from dbplyr or dtplyr). 

2. **`...`**: `<data-masking>` Name-value pairs. The name gives the name of the column in the output. The value can be:
   
   - A vector of length 1, which will be recycled to the correct length.
   
   - A vector the same length as the current group (or the whole data frame if ungrouped).
   
   - `NULL`, to remove the column.
   
   - A data frame or tibble, to create multiple columns in the output.

3. **`.by`**: `<tidy-select>` Optionally, a selection of columns to group by for just this operation, functioning as an alternative to `group_by()`. 

4. **`.keep`**: Control which columns from `.data` are retained in the output. Grouping columns and columns created by `...` are always kept.
   
   - `"all"` retains all columns from `.data`. This is the default.
   
   - `"used"` retains only the columns used in `...` to create new columns. 
   
   - `"unused"` retains only the columns *not* used in `...` to create new columns. 
   
   - `"none"` doesn't retain any extra columns from `.data`. Only the grouping variables and columns created by `...` are kept.

5. **`.before, .after`**: `<tidy-select>` Optionally, control where new columns should appear (the default is to add to the right hand side). The **`.before, .after`** argument can be set to either the <u>column index</u> or the <u>column name</u>.

```r
flights |>
    mutate(
    speed = distance / air_time * 60,
    .before = 1,
    # .after = day,
    .keep = "used"
    )
```

### select

**`select()`** selects columns of a tibble.

```r
# select by name
flights |>
    select(
    # year, month, day,
    # starts_with("abc"),
    # ends_with("xyz"),
    # contains("ijk"),
    # num_range("x", 1:3),  match x1:x3  
)
# select all columns beteen 2 given variables
flights |>
    select(year:day)
# select all columns except those beteen 2 given variables
flights |>
    select(!(year:day))
# select by class
flights |>
    select(where(is.charater))
```

### rename

**`rename()`** renames variables.

```r
flights |>
    rename(tail_num = tailnum)
```

The new name appears on the left-hand side of the `=`, and the old variable appears on the right-hand side.

### relocate

**`relocate()`** changes the order of columns.

```r
# move columns to the front
flights |>
    relocate(time_hour, air_time)
# move columns in a fixed order
flights |>
    relocate(
    year:dep_time, .after = time_hour,
    # starts_with("arr"), .before = dep_time
    )
```

## Group Operators

### group_by

**`group_by()`** adds  grouped feature to the tibble, which <u>changes the behavior of the subsequent verbs applied to the data.</u>

```r
flights |>
    group_by(month, day)
```

### ungroup

**`ungroup()`** removes grouping from a tibble.

```r
daily |>
    ungroup()
```

### summarize

**`summarize()`** calculates summary statistics, reduces the data frame to have a single row for each group. After **`summarize()`**, there will be 1+n columns, where n represents the number of summary statistics.

```r
flights |> 
    group_by(month) |> 
    summarize(
        avg_delay = mean(dep_delay),
        n = n(),
        .groups = "drop_last"
    )
```

1. **`.groups`**:
   
   1. **`"drop"`**  
      
      This option removes all groupings after summarization. The resulting data frame will no longer have any grouping attributes, meaning it behaves like a regular, ungrouped data frame.
   
   2. **`"keep"`**  
      
      This option keeps the original grouping structure. After summarization, the resulting data frame will retain the original groupings, and the class attribute will be maintained.
   
   3. **`"drop_last"`**  
      
      This option drops the last grouping variable. If there were multiple grouping variables, this option will remove the last one while retaining the others. For example, if the data was grouped by `year` and `month`, using `"drop_last"` will result in the data being grouped only by `year` after summarization.

### slice_

`slice_` allows you to extract specific rows within each group.

```r
flights |> 
    group_by(dest) |>
    # takes m rows with largest values of column x from each group
    slice_max(arr_delay, n = m)
    # takes m rows with samllest values of column x from each group
    # slice_min(arr_delay, n = m)
    # take m radom sample from each group
    # slice_sample(n = m)
    # take the first m row from each group
    # slice_head(n = m)
    # take the last m row from each group
    # slice_tail(n = m)


# select 10% of the rows in each group
slice_(prop = 0.1)
# slice without ties
# By default, `with_ties = TRUE`.
slice_max(with_ties = FALSE)
slice_min(with_ties = FALSE)
```

# Data tidying

## Rules that make a dataset clean

1. Each variable is a column; each column is a variable.
2. Each observation is a row; each row is an observation.
3. Each value is a cell; each cell is a single value.

## pivot

`pivot` helps to tidy the datasets.

### Lengthening data

#### pivot_longer

`pivot_longer()` "lengthens" data, increasing the number of rows and decreasing the number of columns.

```r
pivot_longer(
  data,
  cols,
  ...,
  cols_vary = "fastest",
  names_to = "name",
  names_prefix = NULL,
  names_sep = NULL,
  names_pattern = NULL,
  names_ptypes = NULL,
  names_transform = NULL,
  names_repair = "check_unique",
  values_to = "value",
  values_drop_na = FALSE,
  values_ptypes = NULL,
  values_transform = NULL
)
```

1. **`data`**: A data frame to pivot.

2. **`cols`**: `<tidy-select>` Columns to pivot into longer format.

3. **`...`**: Additional arguments passed on to methods.

4. **`cols_vary`**:
   
   When pivoting `cols` into longer format, how should the output rows be arranged relative to their original row number?
   
   - `"fastest"`, the default, keeps individual rows from `cols` close together in the output. This often produces intuitively ordered output when you have at least one key column from `data` that is not involved in the pivoting process.
   
   - `"slowest"` keeps individual columns from `cols` close together in the output. This often produces intuitively ordered output when you utilize all of the columns from `data` in the pivoting process.

5. **`names_to`**:
   
   A character vector specifying the new column or columns to create from the information stored in the column names of `data` specified by `cols`.
   
   - If length 0, or if `NULL` is supplied, no columns will be created.
   
   - If length 1, a single column will be created which will contain the column names specified by `cols`.
   
   - If length >1, multiple columns will be created. In this case, one of `names_sep` or `names_pattern` must be supplied to specify how the column names should be split. 
   
   - `NA` will discard the corresponding component of the column name.
   
   - `".value"` indicates that the corresponding component of the column name defines the name of the output column containing the cell values, overriding `values_to` entirely.

6. **`names_prefix`**:
   
   A regular expression used to remove matching text from the start of each variable name.

7. **`names_sep, names_pattern`**
   
   If **`names_to`** contains multiple values, these arguments control how the column name is broken up.
   
   - **`names_sep`** takes the same specification as **`separate()`**, and can either be a numeric vector (specifying positions to break on), or a single string (specifying a regular expression to split on).
   
   - `names_pattern` takes the same specification as **`extract()`**, a regular expression containing matching groups (`()`).

If these arguments do not give you enough control, use `[pivot_longer_spec()](https://tidyr.tidyverse.org/reference/pivot_longer_spec.html)` to create a spec object and process manually as needed.

names_ptypes, values_ptypes

Optionally, a list of column name-prototype pairs. Alternatively, a single empty prototype can be supplied, which will be applied to all columns. A prototype (or ptype for short) is a zero-length vector (like `[integer()](https://rdrr.io/r/base/integer.html)` or `[numeric()](https://rdrr.io/r/base/numeric.html)`) that defines the type, class, and attributes of a vector. Use these arguments if you want to confirm that the created columns are the types that you expect. Note that if you want to change (instead of confirm) the types of specific columns, you should use `names_transform` or `values_transform` instead.

names_transform, values_transform

Optionally, a list of column name-function pairs. Alternatively, a single function can be supplied, which will be applied to all columns. Use these arguments if you need to change the types of specific columns. For example, `names_transform = list(week = as.integer)` would convert a character variable called `week` to an integer.

If not specified, the type of the columns generated from `names_to` will be character, and the type of the variables generated from `values_to` will be the common type of the input columns used to generate them.

names_repair

What happens if the output has invalid column names? The default, `"check_unique"` is to error if the columns are duplicated. Use `"minimal"` to allow duplicates in the output, or `"unique"` to de-duplicated by adding numeric suffixes. See `[vctrs::vec_as_names()](https://vctrs.r-lib.org/reference/vec_as_names.html)` for more options.

values_to

A string specifying the name of the column to create from the data stored in cell values. If `names_to` is a character containing the special `.value` sentinel, this value will be ignored, and the name of the value column will be derived from part of the existing column names.

values_drop_na

If `TRUE`, will drop rows that contain only `NA`s in the `value_to` column. This effectively converts explicit missing values to implicit missing values, and should generally be used only when missing values in `data` were created by its structure.

#### Data in column names

| artist       | date.entered | wk1 | wk2 | wk3 | wk4 | wk5 |
| ------------ | ------------ | --- | --- | --- | --- | --- |
| 2 Pac        | 2000-02-26   | 87  | 82  | 72  | 77  | 87  |
| 2Ge+her      | 2000-09-02   | 91  | 87  | 92  | NA  | NA  |
| 3 Doors Down | 2000-04-08   | 81  | 70  | 68  | 67  | 66  |
| 3 Doors Down | 2000-10-21   | 76  | 76  | 72  | 69  | 67  |
| 504 Boyz     | 2000-04-15   | 57  | 34  | 25  | 17  | 17  |
| 98^0         | 2000-08-19   | 51  | 39  | 34  | 26  | 26  |

```r
billboard |> 
    pivot_longer(
        cols = starts_with("wk"), 
        names_to = "week", 
        values_to = "rank",
        values_drop_na = TRUE
    )
```

#### Variables in column names

| country     | year | sp_m_014 | sp_m_1524 | sp_f_2534 | sp_m_3544 | sp_m_4554 |
| ----------- | ---- | -------- | --------- | --------- | --------- | --------- |
| Afghanistan | 1980 | NA       | NA        | NA        | NA        | NA        |
| Afghanistan | 1981 | NA       | NA        | NA        | NA        | NA        |
| Afghanistan | 1982 | NA       | NA        | NA        | NA        | NA        |
| Afghanistan | 1983 | NA       | NA        | NA        | NA        | NA        |
| Afghanistan | 1984 | NA       | NA        | NA        | NA        | NA        |
| Afghanistan | 1985 | NA       | NA        | NA        | NA        | NA        |

"**sp**" refers to diagnosis, "**m**" and "**f**" denote gender. "**014**" indicates age between 0 and 14.

```r
who2 |> 
    pivot_longer(
        cols = !(country:year),
        names_to = c("diagnosis", "gender", "age"), 
        names_sep = "_",
        values_to = "count"
    )
```

### Widening data

```r
cms_patient_experience |> 
    pivot_wider(
        names_from = measure_cd,
        values_from = prf_rate
    )
```

## Missing values

#### Identifying NA values

##### During import

```r
read_csv(path, na = )
```

- **`na`** specifies which strings in the data should be interpreted as missing values (`NA`). By default, `na = c("")`(i.e., empty strings are treated as `NA`).

##### na_if

**`na_if(x, y)`** modifies the vector **`x`** by replacing any elements that are equal to **`y`** with `NA`.

```r
na_if(x, y)
```

1. **`x`**: The vector to modify.

2. **`y`**: The value or vector to compare against. **`y`** must either be a single value or have the same length as **`x`**. 
   
   - If **`y`** is a single value, it is recycled to match the length of **`x`** before comparison.
   
   - If **`x`** and **`y`** have the same length, corresponding elements are compared.

##### Implicit missing value

> An explicit missing value is the presence of an absence.  An implicit missing value is the absence of a presence.

```r
stocks <- tibble(
  year  = c(2020, 2020, 2020, 2020, 2021, 2021, 2021),
  qtr   = c(   1,    2,    3,    4,    2,    3,    4),
  price = c(1.88, 0.59, 0.35,   NA, 0.92, 0.17, 2.66)
)
```

- The `price` in the fourth quarter of 2020 is explicitly missing, because its value is `NA`.

- The `price` for the first quarter of 2021 is implicitly missing, because it simply does not appear in the dataset.

###### pivot

Use pivoting to make implicit missings explicit:

```r
stocks |>
  pivot_wider(
    names_from = qtr, 
    values_from = price
  )
#> # A tibble: 2 × 5
#>    year   `1`   `2`   `3`   `4`
#>   <dbl> <dbl> <dbl> <dbl> <dbl>
#> 1  2020  1.88  0.59  0.35 NA   
#> 2  2021 NA     0.92  0.17  2.66
```

###### complete

**`complete()`** turns implicit missing values into explicit missing values. It generates all possible combinations of specified columns including those absent in the original tibble.

```r
complete(data, ..., fill = list(), explicit = TRUE)
```

1. **`data`**: A data frame.

2. **`...`**: 
   
   `<data-masking>`Specification of columns to expand or complete. Columns can be atomic vectors or lists.
   
   - To find all unique combinations of `x`, `y` and `z`, including those not present in the data, supply each variable as a separate argument: `expand(df, x, y, z)` or `complete(df, x, y, z)`.
   
   - To find only the combinations that occur in the data, use `nesting`: ``expand(df, nesting(school_id, student_id), date)` would produce a row for each present school-student combination for all possible dates.
   
   - When used with factors, `complete()` use the full set of levels, not just those that appear in the data. To retain only the factor levels present in the data, use **`forcats::fct_drop()`**.

3. **`fill`**:
   
   A named list that for each variable supplies a single value to use instead of `NA` for missing combinations.

4. **`explicit`**
   
   Should both implicit (newly created) and explicit (pre-existing) missing values be filled by `fill`? By default, this is `TRUE`, but if set to `FALSE` this will limit the fill to only implicit missing values.

```r
df <- tibble(
  group = c(1:2, 1, 2),
  item_id = c(1:2, 2, 3),
  item_name = c("a", "a", "b", "b"),
  value1 = c(1, NA, 3, 4),
  value2 = 4:7
)
df
#> # A tibble: 4 × 5
#>   group item_id item_name value1 value2
#>   <dbl>   <dbl> <chr>      <dbl>  <int>
#> 1     1       1 a              1      4
#> 2     2       2 a             NA      5
#> 3     1       2 b              3      6
#> 4     2       3 b              4      7

# Limit the fill to only the newly created (i.e. previously implicit)
# missing values with `explicit = FALSE`
df %>%
  complete(
    group,
    nesting(item_id, item_name),
    fill = list(value1 = 0, value2 = 99),
    explicit = FALSE
  )
#> # A tibble: 8 × 5
#>   group item_id item_name value1 value2
#>   <dbl>   <dbl> <chr>      <dbl>  <int>
#> 1     1       1 a              1      4
#> 2     1       2 a              0     99
#> 3     1       2 b              3      6
#> 4     1       3 b              0     99
#> 5     2       1 a              0     99
#> 6     2       2 a             NA      5
#> 7     2       2 b              0     99
#> 8     2       3 b              4      7
```

#### Fill missing values

##### LOCF—Last observation carried forward

**`fill()`** takes a set of columns and fills missing values in the selected columns using the next or previous entry.

```r
fill(data, ..., .direction = c("down", "up", "downup", "updown"))
```

1. **`data`**: A data frame.

2. **`...`**: `<tidy-select>` Columns to fill.

3. **`.direction`**: Direction in which to fill missing values. 
   
   - `"down"`: Fills missing values using the nearest non-missing value from above.
   - `"up"`: Fills missing values using the nearest non-missing value from below.
   - `"downup"`: First applies down fill, then fills any remaining missing values using up fill.
   - `"updown"`: First applies up fill, then fills any remaining missing values using down fill.

##### Fixed values

###### coalesce

**`coalesce()`** combines multiple vectors by returning the first non-missing value at each position. If all values at a position are missing (`NA`), the result will also be `NA`.

```r
coalesce(...)
```

```r
y <- c(1, 2, NA, NA, 5)
z <- c(NA, NA, 3, 4, 5)
coalesce(y, z)
#> [1] 1 2 3 4 5
```

###### replace_na

**`replace_na()`** replaces `NA` values in a vector or data frame with a specified replacement value.

```r
replace_na(data, replace)
```

1. **`data`**: A data frame or vector.

2. **`replace`**
   
   - If `data` is a data frame, `replace` takes a named list of values, with one value for each column that has missing values to be replaced. 
   
   - If `data` is a vector, `replace` takes a single value. This single value replaces all of the missing values in the vector. 

```r
# Replace NAs in a data frame
df <- tibble(x = c(1, 2, NA), y = c("a", NA, "b"))
df %>% replace_na(list(x = 0, y = "unknown"))
#> # A tibble: 3 × 2
#>       x y      
#>   <dbl> <chr>  
#> 1     1 a      
#> 2     2 unknown
#> 3     0 b      

# Replace NAs in a vector
df %>% mutate(x = replace_na(x, 0))
#> # A tibble: 3 × 2
#>       x y    
#>   <dbl> <chr>
#> 1     1 a    
#> 2     2 NA   
#> 3     0 b  
```

<u>The replacement value must match the type of the vector or column</u>.  For example:

```r
# Replace NULLs in a list: NULLs are the list-col equivalent of NAs
df_list <- tibble(z = list(1:5, NULL, 10:20))
df_list %>% replace_na(list(z = list(5)))
#> # A tibble: 3 × 1
#>   z         
#>   <list>    
#> 1 <int [5]> 
#> 2 <dbl [1]> 
#> 3 <int [11]>
# if:
df_list %>% replace_na(list(z = 5))
# Error in `vec_assign()`:
# ! Can't convert `replace$z` <double> to match type of `data$z` <list>.
# Run `rlang::last_trace()` to see where the error occurred.
```

# Something else

### Counts

#### count

**`count()`** finds the number of occurrences of the unique rows or distinct combination of some variables in a tibble. 

```r
count(
  x,
  ...,
  wt = NULL,
  sort = FALSE,
  name = NULL,
  .drop = 
)
```

1. **`x`**:
   
   A data frame, data frame extension (e.g. a tibble), or a lazy data frame (e.g. from dbplyr or dtplyr).

2. **`...`**:
   
   `<data-masking>` Variables to group by.

3. **`wt`**:
   
   `<data-masking>` Frequency weights. Can be `NULL` or a variable:
   
   - If `NULL` (the default), counts the number of rows in each group.
   
   - If a variable, computes `sum(wt)` for each group.

4. **`sort`**:
   
   If `TRUE`, you can arrange them in descending order of the number of occurrences.

5. **`name`**:
   
   The name of the new column in the output.
   
   If omitted, it will default to `n`. If there's already a column called `n`, it will use `nn`. If there's a column called `n` and `nn`, it'll use `nnn`, and so on, adding `n`s until it gets a new name.

6. **`.drop`**:
   
   If `FALSE` will include counts for empty groups (i.e. for levels of factors that don't exist in the data).

#### n

**`n()`** only works inside dplyr verbs and doesn't take any arguments.

```r
flights |> 
    group_by(dest) |> 
    summarize(
    n = n()
    )
```

### everything

**`everything()`** selects all variables.

```r
iris %>% select(everything())
```

## last_col

**`last_col()`** select variables from the end.

```
last_col(offset = 0L, vars = NULL)
```

1. **`offset`** : specifies the position offset from the last column.
   
   - If `offset = 0`, the function selects the very last column.
   - If `offset > 0`, it selects the column that is `offset` positions to the left of the last column. For example, `offset = 1` selects the second-to-last column.

2. **`vars`** represents which tibble is to be selected.
   
   ```r
   mtcars %>% select(1:last_col(5))
   #> # A tibble: 32 x 6
   #>     mpg   cyl  disp    hp  drat    wt
   #>   <dbl> <dbl> <dbl> <dbl> <dbl> <dbl>
   #> 1  21       6   160   110  3.9   2.62
   #> 2  21       6   160   110  3.9   2.88
   #> 3  22.8     4   108    93  3.85  2.32
   #> 4  21.4     6   258   110  3.08  3.22
   #> # i 28 more rows
   
   # Example tibble
   data <- tibble(a = 1:5, b = 6:10, c = 11:15)
   # Select the last column
   data %>% select(last_col())
   #> # A tibble: 5 × 1
   #>       c
   #>   <int>
   #> 1    11
   #> 2    12
   #> 3    13
   #> 4    14
   #> 5    15
   # Select the second-to-last column
   data %>% select(last_col(offset = 1))
   #> # A tibble: 5 × 1
   #>       b
   #>   <int>
   #> 1     6
   #> 2     7
   #> 3     8
   #> 4     9
   #> 5    10
   ```

## full_seq

**`full_seq()`** completes an evenly spaced numeric vector by filling in any missing values within the specified interval.

```r
full_seq(x, period)
```

1. **`x`**: A numeric vector.

2. **`period`**: Gap between each observation. The existing data will be checked to ensure that it is actually of this periodicity

```r
full_seq(c(1, 2, 4, 5, 10), 1)
#>  [1]  1  2  3  4  5  6  7  8  9 10
```

# Numeric Operators

## Recycling rules

R's recycling mechanism automatically extends vectors of unequal lengths by repeating the shorter vector to match the length of the longer one. This ensures element-wise operations can be performed even when vectors have different lengths,

## Descriptive statistics

```r
flights |>
    group_by(year, month, day) |>
    summarize(
        mean = mean(dep_delay),
        median = median(dep_delay),
        max = max(dep_delay),
        min = min(dep_delay),
        q95 = quantile(dep_delay, 0.95),
        iqr = IQR(dep_delay), # 0.75-0.25
        first_dep = first(dep_time),
        nth_dep = nth(dep_time, n),
        last_dep = last(dep_time),
    )
```

## Minimum and maximum

### pmin and pmax

**`pmin()`** and **`pmax()`** will return the smallest and largest number in each row when given multiple variables.

```r
df |>
    mutate(
        min = pmin(x, y),
        max = pmax(x, y)
    ) 
```

### min and max

**`min()`** and **`max()`** will return the smallest and largest number in each variable when given multiple variables.

## Rank

## Logarithms

```r
log2(x)
log(x)
log10(x)
```

## Round

### round

**`round(x, digits)`** rounds to the nearest $10^{-n}$ where **`digits`** represents $n$. It performs rounding to the nearest value, following the standard rounding rules (i.e.,<u> values exactly halfway</u> are rounded to the <u>nearest even number</u>).

```r
round(123.456, 2)  # two digits
#> [1] 123.46
round(123.456, 1)  # one digit
#> [1] 123.5
round(123.456, -1) # round to nearest ten
#> [1] 120
round(123.456, -2) # round to nearest hundred
#> [1] 100
round(2.5, 1) # round to nearest even number
#> [1] 2
```

### floor and  ceiling

**`floor()`** always rounds down and **`ceiling()`** always rounds up.

## Cut

**`cut()`** can break up a numeric vector into discrete buckets

```r
x <- c(1, 2, 5, 10, 15, 20)
# (0, 5]->"sm", (5, 10]->"md" ...
cut(x, 
    breaks = c(0, 5, 10, 15, 20), 
    labels = c("sm", "md", "lg", "xl")
)
#> [1] sm sm sm md lg xl
#> Levels: sm md lg xl
```

## Cumulative and rolling aggregates

Base R provides **`cumsum(), cumprod(), cummin(), cummax()`**. dplyr provides **`cummean()`**. More in <u>slider</u> package.

```r
x <- 1:10
cumsum(x)
#>  [1]  1  3  6 10 15 21 28 36 45 55
```

# String Operators

## Creating strings

### Escapes and raw strings

#### Escapes

1. `" \' " `    ` " \" "`

2. `" \\ "`

3. `\t`  `\n`

4. In regular expressions, symbols such as `.`, `$`, `|`, `*`, `+`, `?`, `{`, `}`, `(`, and `)` have special meanings and are used to define patterns. To match these symbols literally, they need to be placed inside a character class, e.g., `[.]`, `[$]`, `[|]`, etc., or escaped with a backslash. This ensures that the symbols are interpreted as their literal values rather than their special functions in regular expression syntax.

#### Raw strings

**`str_view()`** will show raw strings.

`r"()"` will create a raw string. If the string contains `()`, use `r"-()-"` with any number of dashes to avoid conflicts. 

### str_c

**`str_c()`** takes multiple vectors as arguments and concatenates them directly.

```r
df <- tibble(name = c("Flora", "David", "Terra", NA))
# use coalesce to replace missing values in the 'name' column with "you"
df |> mutate(greeting = str_c("Hi ", coalesce(name, "you"), "!"))
```

### str_glue

**`str_glue()`** is an alternative approch for **`str_c()`**.

```r
df |> mutate(greeting = str_glue("Hi {name}!")
```

### str_flatten

```r
df <- tribble(
  ~ name, ~ fruit,
  "Carmen", "banana",
  "Carmen", "apple",
  "Marvin", "nectarine",
  "Terence", "cantaloupe",
  "Terence", "papaya",
  "Terence", "mandarin"
)
df |>
  group_by(name) |> 
  summarize(fruits = str_flatten(fruit, ", "))
#> # A tibble: 3 × 2
#>   name    fruits                      
#>   <chr>   <chr>                       
#> 1 Carmen  banana, apple               
#> 2 Marvin  nectarine                   
#> 3 Terence cantaloupe, papaya, mandarin
```

**`str_flatten(, collapse=",", last = " and")`**

## Extracting data from strings

### parse_

#### parse_number

**`parse_number()`** extracts the first number from a string.

```r
# return 3513
parse_number("USD 3,513")

# return 1
parse_number("A1B2")
```

#### parse_double

**`parse_double()`** converts numbers represented as strings into double-type numeric values. The string <u>must contain only valid numeric characters.</u>

```r
# return 1000.0
parse_double("1e3")
```

### longer

#### seperate_longer_delim

**`seperate_longer_delim(x, delim)`** separats a string into rows based on a delimiter.

```r
df1 <- tibble(x = c("a,b,c", "d,e", "f"))
df1 |> 
  separate_longer_delim(x, delim = ",")
#> # A tibble: 6 × 1
#>   x    
#>   <chr>
#> 1 a    
#> 2 b    
#> 3 c    
#> 4 d    
#> 5 e    
#> 6 f
```

#### seperate_longer_position

**`seperate_longer_position()`** separats a string into rows based on a fixed width, effectively breaking the data into evenly sized segments.

```r
df2 <- tibble(x = c("1211", "131", "21"))
df2 |> 
  separate_longer_position(x, width = 1)
#> # A tibble: 9 × 1
#>   x    
#>   <chr>
#> 1 1    
#> 2 2    
#> 3 1    
#> 4 1    
#> 5 1    
#> 6 3    
#> # ℹ 3 more rows
```

### wider

#### seperate_wider_delim

**`seperate_wider_delim()`** separates a string into columns based on a delimer. Column names should be given.

```r
df3 <- tibble(x = c("a10.1.2022", "b10.2.2011", "e15.1.2015"))
df3 |> 
  separate_wider_delim(
    x,
    delim = ".",
    names = c("code", "edition", "year")
  )
#> # A tibble: 3 × 3
#>   code  edition year 
#>   <chr> <chr>   <chr>
#> 1 a10   1       2022 
#> 2 b10   2       2011 
#> 3 e15   1       2015 
```

#### separate_wider_position

**`seperate_wider_position()`** separates a string into columns based on a fixed width. Column names should be given.

```r
df4 <- tibble(x = c("202215TX", "202122LA", "202325CA")) 
df4 |> 
  separate_wider_position(
    x,
    widths = c(year = 4, age = 2, state = 2)
  )
#> # A tibble: 3 × 3
#>   year  age   state
#>   <chr> <chr> <chr>
#> 1 2022  15    TX   
#> 2 2021  22    LA   
#> 3 2023  25    CA
```

#### separate_wider_regex

**`seperate_wider_regex()`** separates a string into columns based on a regular expression. Column names should be given.

```r
df <- tribble(
  ~str,
  "<Sheryl>-F_34",
  "<Kisha>-F_45", 
  "<Brandon>-N_33",
  "<Sharon>-F_38", 
  "<Penny>-F_58",
  "<Justin>-M_41", 
  "<Patricia>-F_84", 
)
df |> 
  separate_wider_regex(
    str,
    patterns = c(
      "<", 
      name = "[A-Za-z]+", 
      ">-", 
      gender = ".",
      "_",
      age = "[0-9]+"
    )
  )
#> # A tibble: 7 × 3
#>   name    gender age  
#>   <chr>   <chr>  <chr>
#> 1 Sheryl  F      34   
#> 2 Kisha   F      45   
#> 3 Brandon N      33   
#> 4 Sharon  F      38   
#> 5 Penny   F      58   
#> 6 Justin  M      41   
#> # ℹ 1 more row
```

#### debug

If some rows do not contain the expected number of pieces, you can use debugging options in **`separate_wider_delim(), separate_wider_position, separate_wider_regex`** to diagnose and handle the issue. Here's how it works:

```r
debug <- df |> 
  separate_wider_delim(
    x,
    delim = "-",
    names = c("x", "y", "z"),
    # which to use depends on the error message
    too_few = "debug",  # Option to debug rows with too few pieces
    # too_many = "debug" # Option to debug rows with too many pieces
  ) |> filter(!x_ok)

#>   x     y     z     x_ok  x_pieces x_remainder
#>   <chr> <chr> <chr> <lgl>    <int> <chr>      
#> 1 1-1-1 1     1     TRUE         3 ""         
#> 2 1-1-2 1     2     TRUE         3 ""         
#> 3 1-3   3     <NA>  FALSE        2 ""         
#> 4 1-3-2 3     2     TRUE         3 ""         
#> 5 1     <NA>  <NA>  FALSE        1 ""
```

- **`x_ok`**: This column will indicate whether a row succeeded in being split properly. A value of `TRUE` means the row was correctly split into the expected number of pieces; `FALSE` indicates there was an issue.

- **`x_pieces`**: This column will display how many pieces were found when attempting to separate the string. It helps you identify rows with unexpected numbers of segments.

- **`x_reminder`** (if using `too_many`): This column shows any remaining unprocessed characters if there are more segments than expected. For instance, if the string had extra parts beyond the expected number, they will appear in this column.

- **`too_few`** options:
  
  - **`align_start`**: Aligns the available pieces to the start of the expected columns, filling the remaining columns with `NA`.
  - **`align_end`**: Aligns the available pieces to the end of the expected columns, filling the missing columns with `NA`.

- **`too_many`** options:
  
  - **`merge`**: Merges extra pieces into the last column.
  - **`drop`**: Drops any extra pieces beyond the expected columns.

## Letters

### str_length

**`str_length()`** calculates the number of letters in strings.

```r
str_length(c("a", "R for data science", NA))
#> [1]  1 18 NA
```

### str_sub

**`str_sub()`** extracts parts of a string.

```r
x <- c("Apple", "Banana", "Pear")
str_sub(x, 1, 3)
#> [1] "App" "Ban" "Pea"

str_sub(x, -3, -1)
#> [1] "ple" "ana" "ear"
```

## Regular expressions

### Pattern basics

1. `.` matches any character.

2. `+` lets the pattern before it repeat at least once.

3. `?` makes the pattern before it optional(i.e. it matches 0 or 1 times).

4. `*` lets the pattern before it be optional or repeat for any times.

5. `{}` specifies the number of matches precisely.
   
   1. `{n}` matches exactly $n$ times.
   
   2. `{n,}` matches at least $n$ times.
   
   3. `{n,m}` matches between $n$ and $m$ times.

6. `[]` matches a set of characters in it.
   
   1. `[^ ]` matches anything except characters in it.
   
   2. `[A-Z]` matches all uppercase letters while `[a-z]` matches all lowercase letters.
   
   3. `[A-Za-z]` matches all letters.
   
   4. `[0-9]` matches all numbers.

7. `|` represents the "OR" operator.

8. `^` represents the start and `$` represents the end.

9. `[\^\-\]]` matches `^`, `-`, or `]`

10. `\b` matches the boundary between words(i.e. the start or the end of a word). `\bsum\b` matches the exact word "sum", and prevents matches where "sum" is part of a longer word. Search for `\bsum\b` to avoid matching `summarize`, `summary`, `rowsum` and so on.

11. `\d` matches any digit;  
    
    `\D` matches anything that isn’t a digit.
    
    `\s` matches any whitespace (e.g., space, tab, newline);  
    
    `\S` matches anything that isn’t whitespace.
    
    `\w` matches any “word” character, i.e. letters and numbers;  
    
    `\W` matches any “non-word” character.

12. `()` 
    
    1. can override the usual precedence of regular expressions.
    
    2. can create capturing groups with `\n` . $n$ represents for the match in the nth parantheses. For example: 
       
       . `str_view(fruit, "(..)\\1")` finds all fruits that have a repeated pair of letters. 
       
       . `str_view(words, "^(..).*\\1$")` finds all words that start and end with the same pair of letters.
       
       .  `sentences |> str_replace("(\\w+) (\\w+) (\\w+)", "\\1 \\3 \\2")` switches the order of the second and third words in sentences.
    
    3. `(?:)` creates a non capturing group, e.g., `str_match(x, "gr(?:e|a)y")`

Each match starts at the end of the previous match, i.e. regex matches never overlap.

### Functions

#### regex

**`regex()`** creates regular expressions with flags.

```r
regex(reg, ignore_case = TRUE, dotall = TRUE, 
      multiline = TRUE, comments = TRUE)
```

1. **`ignore_case`** controls whether the regular expression matches both uppercase and lowercase forms of characters. When set to `TRUE`, the regular expression will treat characters case-insensitively.

2. **`dotall`** allows the dot (`.`) in a regular expression to match any character, including newlines (`\n`). By default, the dot matches any character except for a newline, but with `dotall` enabled, it extends to include newlines as well.

3. **`multiline`** affects the behavior of the `^` (start of line) and `$` (end of line) anchors. With `multiline` enabled, these anchors match the beginning and end of each line (not just the start and end of the entire string). This is particularly useful when the string represents a multiline sentence.

4. **`comments`** allows you to use comments and whitespace to make complex regular expressions more understandable. 

When using comments in a regular expression and needing to match a space, newline, or the `#` character, it's necessary to <u>escape them with a backslash</u> (`\`) to prevent confusion with the comment syntax.

#### str_view

**`str_view()`** not only displays the raw strings, but also highlights the matched portions by enclosing them in `<>` when a regular expression is provided.

```r
x <- "Line 1\nLine 2\nLine 3"
str_view(x, "^Line")
#> [1] │ <Line> 1
#>     │ Line 2
#>     │ Line 3
str_view(x, regex("^Line", multiline = TRUE))
#> [1] │ <Line> 1
#>     │ <Line> 2
#>     │ <Line> 3str_view() not only displays the raw strings, but also highlights the matched portions by enclosing them in <> when a regular expression is provided.
```

#### str_detect

**`str_detect()`** returns a logical vector that is `TRUE` if the pattern matches an element of the character vector and `FALSE` otherwise.

```r
str_detect(c("ab", "b", "c"), "[aeiou]")
#> [1]  TRUE FALSE FALSE
```

<u>Note that **`str_detect()`** can be used for boolean indexing.</u>

#### str_subset

**`str_subset()`** returns a character vector containing only the strings that match.

```r
str_subset(c("ab", "b", "c"), "[aeiou]")
#> [1]  "ab"
```

#### str_which

**`str_which()`** returns an integer vector giving the positions of the strings that match.

```r
str_which(c("ab", "b", "c"), "[aeiou]")
#> [1]  1
```

#### str_count

**`str_count`** returns how many matches there are <u>in each string</u>.

```r
x <- c("apple", "banana", "pear")
str_count(x, "p")
#> [1] 2 0 1
```

#### str_match

**`str_match()`** returns a matrix with the entire match and captured groups.

```r
sentences |> 
  str_match("the (\\w+) (\\w+)")
#>      [,1]                [,2]     [,3]    
#> [1,] "the smooth planks" "smooth" "planks"
#> [2,] "the sheet to"      "sheet"  "to"    
#> [3,] "the depth of"      "depth"  "of"    
#> [4,] NA                  NA       NA      
#> [5,] NA                  NA       NA      
#> [6,] NA                  NA       NA  
```

If the match failed, **`str_match()`** will return `NA`.

#### Replace

##### str_replace

**`str_replace()`** replaces the first match.

```r
x <- c("apple", "pear", "banana")
str_replace_all(x, "[aeiou]", "-")
#> [1] "-pple"  "p-ar"   "b-nana"
```

##### str_replace_all

**`str_replace_all()`** replaces all matches.

```r
x <- c("apple", "pear", "banana")
str_replace_all(x, "[aeiou]", "-")
#> [1] "-ppl-"  "p--r"   "b-n-n-"
```

#### Remove

##### str_remove

**`str_remove`** removes the first match.

```r
x <- c("apple", "pear", "banana")
str_remove(x, "[aeiou]")
#> [1] "pple"  "par"   "bnana"
```

##### str_remove_all

**`str_remove_all()`** removes all matches.

```r
x <- c("apple", "pear", "banana")
str_replace_all(x, "[aeiou]")
#> [1] "ppl"  "pr"   "bnn"
```

# Factor Operators

## fct

Use `forcats::fct()` , not `factor` in base R.

```r
x <- c("Dec", "Apr", "Jan", "Mar")
month_levels <- c(
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
)
factor <- fct(x, levels = month_levels)`
```

With `forcats::fct()`:

1. After converting to a **`factor`**, **`sort()`** sorts the data by categories, rather than the raw data values. The **`factor`** type preserves the category information, which facilitates ordered operations and comparisons.

```r
sort(x)
#> [1] Jan Mar Apr Dec
#> Levels: Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dam"
```

2. When converting to a `factor`, all values must appear in the specified `levels`. If there are missing categories, R throws an error, helping ensure data integrity.

```r
x <- c("Dec", "Apr", "Jam", "Mar")
month_levels <- c(
  "Jan", "Feb", "Mar", "Apr", "May", "Jun",
  "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
)
y <- fct(x, levels = month_levels)
#> Error in `fct()`:
#> ! All values of `x` must appear in `levels` or `na`
#> ℹ Missing level: "Jam"
```

## levels

**`levels()`** helps access to the set of valid levels directly. 

```r
levels(x)
```

`x` should be a factor.

## ordered

**`ordered()`** creates ordered factors. Ordered factors imply a strict ordering between levels, but don’t specify anything about the magnitude of the differences between the levels. 

An ordered factor can be recognized in its printed output, as it uses `<` symbols between the factor levels:

```r
ordered(c("a", "b", "c")) 
#> [1] a b c 
#> Levels: a < b < c`
```

In both base R and the tidyverse, ordered factors behave similarly to regular factors, with two notable differences:

- When an ordered factor is mapped to color or fill in ggplot2, it defaults to **`scale_color_viridis()`** or **`scale_fill_viridis()`**, color scales that imply a ranking.
- When used as a predictor in a linear model, an ordered factor applies “polynomial contrasts.” While these can be useful, they are rarely interpreted unless specialized statistical knowledge is applied. For further details, refer to **`vignette("contrasts", package = "faux")`** by Lisa DeBruine.

## Modifying factor order

The functions mentioned below <u>do not actually modify the order of factor levels in memory. </u>Instead, they affect the order used in subsequent operations that involve the factor. The underlying factor levels remain the same, but the way they are handled or displayed is adjusted for specific tasks.

### fct_inorder

**`fct_inorder()`** reorders levels by order in which 
they appear in the data.

```r
fct_inorder(f)
```

### fct_reorder

**`fct_reorder()`** reorders the levels of a factor based on a numeric vector, typically by a function applied to the vector (e.g., median, mean, etc.). The function sorts the levels in ascending order by default, according to the values in the numeric vector.

```r
fct_reorder(.f = , .x = , .fun = median, desc = FALSE)
```

1. **`.f`** represents the factor whose levels need to be modified.

2. **`.x`** represents the numeric vector used to reorder the levels. It must have the same length as the factor.

3. **`.fun`**  represents the function applied to **`.x`** for each level of **`.f`** .

### fct_reorder2

**`fct_reorder2()`** reorders the levels of a factor based on 2 numeric vectors.

```r
fct_reorder2(.f = , .x = , .y = , .fun = , .desc = TRUE )
```

1. **`.f`** represents the factor whose levels are to be reordered.

2. **`.x`** and **`.y`** are two numeric vectors used to determine the reordering. Specifically, the function first sorts the data based on `.x`. Then, it applies the specified function `.fun` to the `.y` values corresponding to the sorted `.x`, and uses the result to reorder the levels of the factor.

3. **`.fun`** :
   
   1. **`last2`**: After sorting **`.x`** in ascending order, it takes the corresponding **`.y`** value associated with the last value of **`.x`** (i.e., the largest value in **`.x`** )
   
   2. **`first2`**: After sorting **`.x`** in ascending order, it takes the corresponding `.y` value associated with the first value of **`.x`** (i.e., the smallest value in **`.x`**).

4. **`.desc`** is boolean value indicating whether to reorder the levels in descending order based on the selected `.y`.

### fct_relevel

**`fct_relevel()`** reorders the levels of a factor by moving specified levels to a specified place.

```r
fct_relevel(.f = , ..., after = )
```

1. **`.f`** represents the factor whose levels are to be reordered.
2. **`...`** specifies the levels to be moved to the front.
3. **`after`** indicates the position after which the specified levels should be placed (default is `0`, meaning the levels will be moved to the front).

### fct_infreq

**`fct_infreq()`** reorders factor levels based on their frequencies, in descending order.

```r
fct_infreq(f, w = NULL)
```

1. **`f`** represents the factor whose levels are to be reordered.

2. **`w`** represents the optional weights used to calculate the frequencies. 

### fct_rev

**`fct_rev()`** reverses the order of factor levels.

```r
fct_rev(f)
```

## Modifying factor levels

The functions described below <u>do not modify the underlying levels of a factor in memory.</u> Instead, they adjust how the levels are treated or displayed in subsequent operations involving the factor. While the factor’s original levels remain unchanged, these functions alter their behavior or appearance for specific tasks.

### fct_recode

**`fct_recode()`** changes the value of each level.

```r
gss_cat |> count(partyid)
#> # A tibble: 10 × 2
#>   partyid                n
#>   <fct>              <int>
#> 1 No answer            154
#> 2 Don't know             1
#> 3 Other party          393
#> 4 Strong republican   2314
#> 5 Not str republican  3032
#> 6 Ind,near rep        1791
#> # ℹ 4 more rows
gss_cat |>
  mutate(
    partyid = fct_recode(partyid,
      "Republican, strong"    = "Strong republican",
      "Republican, weak"      = "Not str republican",
      "Independent, near rep" = "Ind,near rep",
      "Independent, near dem" = "Ind,near dem",
      "Democrat, weak"        = "Not str democrat",
      "Democrat, strong"      = "Strong democrat"
    )
  ) |>
  count(partyid)
#> # A tibble: 10 × 2
#>   partyid                   n
#>   <fct>                 <int>
#> 1 No answer               154
#> 2 Don't know                1
#> 3 Other party             393
#> 4 Republican, strong     2314
#> 5 Republican, weak       3032
#> 6 Independent, near rep  1791
#> # ℹ 4 more rows
```

### fct_collapse

**`fct_collapse()`** collapses levels of a factor.

```r
gss_cat |>
  mutate(
    partyid = fct_collapse(partyid,
      "other" = c("No answer", "Don't know", "Other party"),
      "rep" = c("Strong republican", "Not str republican"),
      "ind" = c("Ind,near rep", "Independent", "Ind,near dem"),
      "dem" = c("Not str democrat", "Strong democrat")
    )
  ) |>
  count(partyid)
#> # A tibble: 4 × 2
#>   partyid     n
#>   <fct>   <int>
#> 1 other     548
#> 2 rep      5346
#> 3 ind      8409
#> 4 dem      7180
```

### fct_lump_

All `fct_lump_()` functions share the following parameters:

1. **`f`**: The factor whose levels are to be lumped.
2. **`w`**: An optional numeric vector of weights for frequency of each value (not level) in `f`. If `NULL`, all values are weighted equally.
3. **`other_level`**: A string specifying the name of the new level that combines lumped levels. The default value is `"Other"`.

#### fct_lump_lowfreq

**`fct_lump_lowfreq()`** lumps together the least frequent levels, ensuring that the resulting "other" level always corresponds to the least frequent level among the factor levels.

```r
fct_lump_lowfreq(f, w = NULL, other_level = "Other")
```

#### fct_lump_n

**`fct_lump_n()`** lumps all levels except for the `n` most frequent (or least frequent if `n < 0`).

```r
fct_lump_n(
  f,
  n,
  w = NULL,
  other_level = "Other",
  ties.method = c("min", "average", "first", "last", "random", "max")
)
```

1. **`n`**: The number of the most frequent levels to retain. 

2. **`ties.method`**: Determines how ties in frequency are handled when the number of levels with equal frequency exceeds `n`. Options include:
   
   1. `"min"`: Assigns the smallest rank to tied values.
   2. `"average"`: Assigns the average rank to tied values.
   3. `"first"`: Ranks tied values based on their first occurrence.
   4. `"last"`: Ranks tied values based on their last occurrence.
   5. `"random"`: Breaks ties randomly.
   6. `"max"`: Assigns the largest rank to tied values.

#### fct_lump_min

**`fct_lump_min()`** lumps levels that appear fewer than `min` times.

```r
fct_lump_min(f, min, w = NULL, other_level = "Other")
```

1. **`min`**: A numeric value specifying the minimum number of times a level must appear to remain as a separate level. Levels with fewer occurrences than `min` are lumped together into the "other" level.

#### fct_lump_prop

**`fct_lump_prop()`** lumps levels that appear in fewer than or equal to a specified proportion (`prop`) of the total weight.

```r
fct_lump_prop(f, prop, w = NULL, other_level = "Other")
```

1. **`prop`**: A numeric value between 0 and 1 that specifies the minimum proportion of the total weight (or total occurrences if `w` is `NULL`) a level must have to remain as a separate level. Levels with proportions less than or equal to `prop` are lumped together.

### fct_drop

**`fct_drop()`** drops levels which aren't present in the factor.

```r
fct_drop(f, only = NULL)
```

1. **`f`**: A factor (or character vector).

2. **`only`**: A character vector restricting the set of levels to be dropped. If supplied, only levels that have no entries and appear in this vector will be removed.

```r
f <- factor(c("a", "b"), levels = c("a", "b", "c"))
f
#> [1] a b
#> Levels: a b c
fct_drop(f)
#> [1] a b
#> Levels: a b

# Set only to restrict which levels to drop
fct_drop(f, only = "a")
#> [1] a b
#> Levels: a b c
fct_drop(f, only = "c")
#> [1] a b
#> Levels: a b
```

# Time Operators

## Introduction

There are three types of date/time data that refer to an instant in time:

- A **date**. Tibbles print this as `<date>`.

- A **time** within a day. Tibbles print this as `<time>`.

- A **date-time** is a date plus a time: it uniquely identifies an instant in time (typically to the nearest second). Tibbles print this as `<dttm>`. Base R calls these POSIXct,.

```r
today()
#> [1] "2024-12-06"
now()
#> [1] "2024-12-06 23:08:32 UTC"
```

| Type  | Code  | Meaning                        | Example         |
| ----- | ----- | ------------------------------ | --------------- |
| Year  | `%Y`  | 4 digit year                   | 2021            |
|       | `%y`  | 2 digit year                   | 21              |
| Month | `%m`  | Number                         | 2               |
|       | `%b`  | Abbreviated name               | Feb             |
|       | `%B`  | Full name                      | February        |
| Day   | `%d`  | One or two digits              | 2               |
|       | `%e`  | Two digits                     | 02              |
| Time  | `%H`  | 24-hour hour                   | 13              |
|       | `%I`  | 12-hour hour                   | 1               |
|       | `%p`  | AM/PM                          | pm              |
|       | `%M`  | Minutes                        | 35              |
|       | `%S`  | Seconds                        | 45              |
|       | `%OS` | Seconds with decimal component | 45.35           |
|       | `%Z`  | Time zone name                 | America/Chicago |
|       | `%z`  | Offset from UTC                | +0800           |
| Other | `%.`  | Skip one non-digit             | :               |
|       | `%*`  | Skip any number of non-digits  | # Functions     |

## Creating date/times

### During import

#### ISO8601

ISO8601 Is an international standard for writing dates where the components of a date are organized from biggest to smallest separated by `-`. For example, in ISO8601 May 3 2022 is `2022-05-03`. ISO8601 dates can also include times, where hour, minute, and second are separated by `:`, and the date and time components are separated by either a `T` or a space. (i.e., `2022-05-03 16:26:43` or `2022-05-03T16:26:43`).

If CSV contains an ISO8601 date or date-time, **readr** will automatically recognize it.

```r
csv <- "
  date,datetime
  2022-01-02,2022-01-02 05:12
"
read_csv(csv)
#> # A tibble: 1 × 2
#>   date       datetime           
#>   <date>     <dttm>             
#> 1 2022-01-02 2022-01-02 05:12:00
```

#### col_

**`col_`** functions is used in **readr** for parsing columns in a dataset when importing it (e.g., with **`read_csv()`** or **`read_tsv()`**). They allow precise specification of the column type for better control over data interpretation.

1. **`col_data(format = )`**

2. **`col_time(format = )`**

3. **`col_datetime(format = )`**

**`format`**: A character string specifying the expected input format for the column data.

```r
data <- "date,time,datetime
2023-12-07,14:30:00,2023-12-07 14:30:00
2023-12-08,15:45:00,2023-12-08 15:45:00"

# Read and specify column types
df <- read_csv(data, col_types = cols(
  date = col_date(format = "%Y-%m-%d"),
  time = col_time(format = "%H:%M:%S"),
  datetime = col_datetime(format = "%Y-%m-%d %H:%M:%S")
))
```

### From strings

1. **date**:
   
   - **`ymd(...)`**
   - **`ydm(...)`**
   - **`mdy(...)`**
   - **`myd(...)`**
   - **`dmy(...)`**
   - **`dym(...)`**
   - **`ym(...)`**
   - **`my(...)`**

2. **time**:
   
   - **`hms(...)`**
   - **`hm(...)`**
   - **`ms(...)`**

3. **datetime**:
   
   - **`ymd_hms(...)`**
   - **`ymd_hm(...)`**
   - **`ymd_h(...)`**
   - **`dmy_hms(...)`**
   - **`dmy_hm(...)`**
   - **`dmy_h(...)`**
   - **`mdy_hms(...)`**
   - **`mdy_hm(...)`**
   - **`mdy_h(...)`**
   - **`ydm_hms(...)`**
   - **`ydm_hm(...)`**
   - **`ydm_h(...)`**

4. **others**:
   
   - **`yq(...)`** :
     
     Parse a date-time format where the **year** is followed by the **quarter**.
     
     ```r
     yq("2022 Q1")
     #> "2022-01-01"
     yq("2022 Q2")
     #> "2022-04-01"
     yq("2022 Q3")
     #> "2022-07-01"
     yq("2022 Q1")
     #> "2022-10-01"
     ```

---

- `(...)`: The location where the date-time input string to be parsed should be placed.

These functions in **lubridate** automatically fill in missing components such as day, minute, or second with default values (e.g., day defaults to `1`, minute to `00`, and second to `00`), ensuring smooth parsing of incomplete inputs.

### From individual components

1. **`make_date(year = , month = , day = )`**

2. **`make_date_time(year = , month = , day = , hour = , min = , sec = , tz = "UTC")`**

---

- **year**: numeric year

- **month**: numeric month

- **day**: numeric day

- **hour**: numeric hour

- **min**: numeric minute

- **sec**: numeric second

- **tz**: time zone. Defaults to UTC.

```r
flights |> 
  select(year, month, day, hour, minute) |> 
  mutate(departure = make_datetime(year, month, day, hour, minute))
#> # A tibble: 336,776 × 6
#>    year month   day  hour minute departure          
#>   <int> <int> <int> <dbl>  <dbl> <dttm>             
#> 1  2013     1     1     5     15 2013-01-01 05:15:00
#> 2  2013     1     1     5     29 2013-01-01 05:29:00
#> 3  2013     1     1     5     40 2013-01-01 05:40:00
#> 4  2013     1     1     5     45 2013-01-01 05:45:00
#> 5  2013     1     1     6      0 2013-01-01 06:00:00
#> 6  2013     1     1     5     58 2013-01-01 05:58:00
#> # ℹ 336,770 more rows
```

### From other types

1. **`as_date(...)`**

2. **`as_datatime(...)`**

For example: 

```r
as_datetime(today())
#> [1] "2024-12-06 UTC"
as_date(now())
#> [1] "2024-12-06"
```

### update

**`update()`** can create a new date-time.

```r
update(datetime, year = 2030, month = 2, mday = 2, hour = 2)
#> [1] "2030-02-02 02:34:56 UTC"
```

## Getting Components

1. **`date(x)`**

2. **`year(x)`**

3. **`month(x, label, abbr)`**

4. **day**:
   
   - **`wday(x, label, abbr)`**: The day of the week.
   
   - **`mday(x)`**: The day of the month.
   
   - **`qday(x)`**: The day of the quarter.
   
   - **`yday(x)`**: The day of the year.

5. **`hour(x)`**

6. **`minute(x)`**

7. **`second(x)`**

8. **`tz(x)`**: Time zone.

9. **`quarter(x)`**

10. **`semester(x, with_year)`**

11. **am** and **pm**:
    
    - **`am(x)`**
    
    - **`pm(x)`**

12. **`leap_year(x)`**

13. **`dst(x)`**: Daylight savings.

---

- **`x`**: A date-time object from which components will be extracted.

- **`label`**: A logical value applicable to **`wday()`** and **`month()`**.
  
  - Defaults to `FALSE`, which returns numeric representations (e.g., 1-7 for weekdays, or 1-12 for months).

- **`abbr`**: A logical value used with **`label = TRUE`** in **`wday()`** and **`month()`**.
  
  - If `TRUE`, the function returns an abbreviated **ordered factor** (e.g., "Mon" for **`wday()`**, or "Jan" for **`month()`**).
  - Defaults to `TRUE`. Set to `FALSE` for full names.

- **`with_year`**: A logical value applicable to **`semester()`**. If `TRUE`, the function returns semesters with years.

--- 

These functions can also modify components of a date/time.

```r
(datetime <- ymd_hms("2026-07-08 12:34:56"))
#> [1] "2026-07-08 12:34:56 UTC"

year(datetime) <- 2030
datetime
#> [1] "2030-07-08 12:34:56 UTC"
month(datetime) <- 01
datetime
#> [1] "2030-01-08 12:34:56 UTC"
hour(datetime) <- hour(datetime) + 1
datetime
#> [1] "2030-01-08 13:34:56 UTC"
```

## Time spans

### Duration

#### as.duration

```r
# How old is Hadley?
h_age <- today() - ymd("1979-10-14")
h_age
#> Time difference of 16490 days
as.duration(h_age)
#> [1] "1424736000s (~45.15 years)"
```

#### is.duration

#### duration

**`duration()`** creates a duration object with the specified values. Durations always record the time span in seconds.

```r
duration(num = NULL, units = "second", ...)
```

1. **`num`**
   
   The number or a character vector of time units. In string representation all unambiguous name units and abbreviations and ISO 8601 formats are supported; 'm' stands for month and 'M' for minutes unless ISO 8601 "P" modifier is present (see examples). Fractional units are supported.

2. **`units`**
   
   A character string that specifies the type of units that **`num`** refers to. When **`num`** is character, this argument is ignored.

```r
duration(90, "seconds")
#> [1] "90s (~1.5 minutes)"
duration(second = 3, minute = 1.5, hour = 2, day = 6, week = 1)
#> [1] "1130493s (~1.87 weeks)"
duration("2hours 2minutes 1second")
#> [1] "7321s (~2.03 hours)"
```

Using durations for calculations may potentially alter the time zone of the resulting date-time object. So there is **`Period()`**.

```r
x <- ymd("2009-08-03", tz = "America/Chicago")
x + ddays(1) + dhours(6) + dminutes(30)
#> [1] "2009-08-04 06:30:00 CDT"
x + ddays(100) - dhours(8)
#> [1] "2009-11-10 15:00:00 CST"
```

### Period

**`period()`** creates a period object with the specified values.

```r
period(num = NULL, units = "second", ...)
```

1. **`num`**
   
   a numeric or character vector. A character vector can specify periods in a convenient shorthand format or ISO 8601 specification. All unambiguous name units and abbreviations are supported, "m" stands for months, "M" for minutes unless ISO 8601 "P" modifier is present. Fractional units are supported but the fractional part is always converted to seconds.

2. **`units`**
   
   A character vector that lists the type of units to be used. The units in units are matched to the values in num according to their order. When **`num`** is character, this argument is ignored.

```r
period(c(3, 1, 2, 13, 1), c("second", "minute", "hour", "day", "week"))
#> [1] "20d 2H 1M 3S"
period(second = 90, minute = 5)
#> [1] "5M 90S"
period("2hours 2minutes 1second")
#> [1] "2H 2M 1S"
ymd("2009-08-03") + period(1, "day")
#> [1] "2009-08-04" 
```

### Intervals

When dividing periods, the result reflects the average conversion between the units:

```r
years(1) / days(1) 
#> [1] 365.25
```

This indicates one year is equivalent to an average of 365.25 days.

Intervals represent time spans bettween two specific date-time points and allow division. Use **`%--%`** to create an interval.

```r
y2023 <- ymd("2023-01-01") %--% ymd("2024-01-01")
y2023
#> [1] 2023-01-01 UTC--2024-01-01 UTC
y2023 / days(1)
#> [1] 365
```

## Round

### round_date

**`round_date()`** takes a date-time object and time unit, and rounds it to the nearest value of the specified time unit.<u> For rounding date-times which are exactly halfway between two consecutive units, the convention is to round up.</u>

```r
round_date(x, unit = )
```

1. **`x`**: a vector of date-time objects.

2. **`unit`**: A string, Period object or a date-time object. 

### floor_date and ceiling date

**`floor_date()`** always rounds down and **`ceiling_date()`** always rounds up.

# Functions

## Data frame functions

### Tidy selections and data-masking

Based on the principles outlined in the [Tidyverse Official Article on Programming with dplyr](https://dplyr.tidyverse.org/articles/programming.html), it is possible to create custom functions that incorporate **dplyr** operations by using the `{{` syntax. This syntax enables function arguments to directly refer to column names, avoiding the need to use the `$` operator for explicit column indexing. This design utilizes **tidy evaluation**, which underpins two key mechanisms in dplyr:

1. **Data masking**: Utilized in functions such as **`arrange()`**, **`count()`**, **`filter()`**, **`group_by()`**, **`mutate()`**, and **`summarise()`** where operations are performed on the values within columns.
2. **Tidy selection**: Applied in functions like **`across()`**, **`pull()`**, **`select()`**, **`relocate()`**, and **`rename()`** where operations are performed with column names.

 **`pick()`** function allows you to use tidy-selection inside data-masking functions. This combination provides a concise and efficient method for interacting with both column names and their values within the same context.

For example:

```r
my_function <- function(data, col) {   
data %>%     
    mutate(selected_mean = rowMeans(pick({{ col }}))) }
```

# Iterations
