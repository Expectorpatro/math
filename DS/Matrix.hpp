#pragma once

#include "Vector.hpp"

#include <stdexcept>
#include <type_traits>

#if defined(__AVX__)
#include <immintrin.h>
#endif

template <typename T>
class Matrix
{
private:
    Rank _rows{};
    Rank _cols{};
    Vector<T> _data{};

    static Rank min(Rank a, Rank b)
    {
        return (a < b) ? a : b;
    }

    void checkMul(Matrix<T> const &rhs) const
    {
        if (_cols != rhs._rows)
            throw std::invalid_argument{"Matrix dimensions do not match"};
    }

#if defined(__AVX__) && defined(__FMA__)
    static void avxSIMD(T const &a, T const *rhsRow, T *resultRow, Rank begin, Rank end)
    {
        if constexpr (std::is_same<T, float>::value)
        {
            __m256 va{_mm256_set1_ps(a)};
            Rank j{begin};

            for (; j + 7 < end; j += 8)
            {
                __m256 vb{_mm256_loadu_ps(rhsRow + j)};
                __m256 vc{_mm256_loadu_ps(resultRow + j)};
                vc = _mm256_fmadd_ps(va, vb, vc);
                _mm256_storeu_ps(resultRow + j, vc);
            }

            for (; j < end; ++j)
                resultRow[j] += a * rhsRow[j];
        }
        else if constexpr (std::is_same<T, double>::value)
        {
            __m256d va{_mm256_set1_pd(a)};
            Rank j{begin};

            for (; j + 3 < end; j += 4)
            {
                __m256d vb{_mm256_loadu_pd(rhsRow + j)};
                __m256d vc{_mm256_loadu_pd(resultRow + j)};
                vc = _mm256_fmadd_pd(va, vb, vc);
                _mm256_storeu_pd(resultRow + j, vc);
            }

            for (; j < end; ++j)
                resultRow[j] += a * rhsRow[j];
        }
    }

    void avxMicroKernel(Matrix<T> const &rhs,
                        Matrix<T> &result,
                        Rank iBegin,
                        Rank kBegin,
                        Rank kEnd,
                        Rank jBegin) const
    {
        if constexpr (std::is_same<T, float>::value)
        {
            __m256 c00{_mm256_loadu_ps(&result._data[iBegin * rhs._cols + jBegin])};
            __m256 c01{_mm256_loadu_ps(&result._data[iBegin * rhs._cols + jBegin + 8])};
            __m256 c10{_mm256_loadu_ps(&result._data[(iBegin + 1) * rhs._cols + jBegin])};
            __m256 c11{_mm256_loadu_ps(&result._data[(iBegin + 1) * rhs._cols + jBegin + 8])};
            __m256 c20{_mm256_loadu_ps(&result._data[(iBegin + 2) * rhs._cols + jBegin])};
            __m256 c21{_mm256_loadu_ps(&result._data[(iBegin + 2) * rhs._cols + jBegin + 8])};
            __m256 c30{_mm256_loadu_ps(&result._data[(iBegin + 3) * rhs._cols + jBegin])};
            __m256 c31{_mm256_loadu_ps(&result._data[(iBegin + 3) * rhs._cols + jBegin + 8])};

            for (Rank k{kBegin}; k < kEnd; ++k)
            {
                __m256 b0{_mm256_loadu_ps(&rhs._data[k * rhs._cols + jBegin])};
                __m256 b1{_mm256_loadu_ps(&rhs._data[k * rhs._cols + jBegin + 8])};

                __m256 a{_mm256_set1_ps(_data[iBegin * _cols + k])};
                c00 = _mm256_fmadd_ps(a, b0, c00);
                c01 = _mm256_fmadd_ps(a, b1, c01);

                a = _mm256_set1_ps(_data[(iBegin + 1) * _cols + k]);
                c10 = _mm256_fmadd_ps(a, b0, c10);
                c11 = _mm256_fmadd_ps(a, b1, c11);

                a = _mm256_set1_ps(_data[(iBegin + 2) * _cols + k]);
                c20 = _mm256_fmadd_ps(a, b0, c20);
                c21 = _mm256_fmadd_ps(a, b1, c21);

                a = _mm256_set1_ps(_data[(iBegin + 3) * _cols + k]);
                c30 = _mm256_fmadd_ps(a, b0, c30);
                c31 = _mm256_fmadd_ps(a, b1, c31);
            }

            _mm256_storeu_ps(&result._data[iBegin * rhs._cols + jBegin], c00);
            _mm256_storeu_ps(&result._data[iBegin * rhs._cols + jBegin + 8], c01);
            _mm256_storeu_ps(&result._data[(iBegin + 1) * rhs._cols + jBegin], c10);
            _mm256_storeu_ps(&result._data[(iBegin + 1) * rhs._cols + jBegin + 8], c11);
            _mm256_storeu_ps(&result._data[(iBegin + 2) * rhs._cols + jBegin], c20);
            _mm256_storeu_ps(&result._data[(iBegin + 2) * rhs._cols + jBegin + 8], c21);
            _mm256_storeu_ps(&result._data[(iBegin + 3) * rhs._cols + jBegin], c30);
            _mm256_storeu_ps(&result._data[(iBegin + 3) * rhs._cols + jBegin + 8], c31);
        }
        else if constexpr (std::is_same<T, double>::value)
        {
            __m256d c00{_mm256_loadu_pd(&result._data[iBegin * rhs._cols + jBegin])};
            __m256d c01{_mm256_loadu_pd(&result._data[iBegin * rhs._cols + jBegin + 4])};
            __m256d c10{_mm256_loadu_pd(&result._data[(iBegin + 1) * rhs._cols + jBegin])};
            __m256d c11{_mm256_loadu_pd(&result._data[(iBegin + 1) * rhs._cols + jBegin + 4])};
            __m256d c20{_mm256_loadu_pd(&result._data[(iBegin + 2) * rhs._cols + jBegin])};
            __m256d c21{_mm256_loadu_pd(&result._data[(iBegin + 2) * rhs._cols + jBegin + 4])};
            __m256d c30{_mm256_loadu_pd(&result._data[(iBegin + 3) * rhs._cols + jBegin])};
            __m256d c31{_mm256_loadu_pd(&result._data[(iBegin + 3) * rhs._cols + jBegin + 4])};

            for (Rank k{kBegin}; k < kEnd; ++k)
            {
                __m256d b0{_mm256_loadu_pd(&rhs._data[k * rhs._cols + jBegin])};
                __m256d b1{_mm256_loadu_pd(&rhs._data[k * rhs._cols + jBegin + 4])};

                __m256 a{_mm256_set1_pd(_data[iBegin * _cols + k])};
                c00 = _mm256_fmadd_pd(a, b0, c00);
                c01 = _mm256_fmadd_pd(a, b1, c01);

                a = _mm256_set1_pd(_data[(iBegin + 1) * _cols + k]);
                c10 = _mm256_fmadd_pd(a, b0, c10);
                c11 = _mm256_fmadd_pd(a, b1, c11);

                a = _mm256_set1_pd(_data[(iBegin + 2) * _cols + k]);
                c20 = _mm256_fmadd_pd(a, b0, c20);
                c21 = _mm256_fmadd_pd(a, b1, c21);

                a = _mm256_set1_pd(_data[(iBegin + 3) * _cols + k]);
                c30 = _mm256_fmadd_pd(a, b0, c30);
                c31 = _mm256_fmadd_pd(a, b1, c31);
            }

            _mm256_storeu_pd(&result._data[iBegin * rhs._cols + jBegin], c00);
            _mm256_storeu_pd(&result._data[iBegin * rhs._cols + jBegin + 4], c01);
            _mm256_storeu_pd(&result._data[(iBegin + 1) * rhs._cols + jBegin], c10);
            _mm256_storeu_pd(&result._data[(iBegin + 1) * rhs._cols + jBegin + 4], c11);
            _mm256_storeu_pd(&result._data[(iBegin + 2) * rhs._cols + jBegin], c20);
            _mm256_storeu_pd(&result._data[(iBegin + 2) * rhs._cols + jBegin + 4], c21);
            _mm256_storeu_pd(&result._data[(iBegin + 3) * rhs._cols + jBegin], c30);
            _mm256_storeu_pd(&result._data[(iBegin + 3) * rhs._cols + jBegin + 4], c31);
        }
    }
#endif

public:
    Matrix(Rank rows = 0,
           Rank cols = 0,
           T const &value = T{})
        : _rows{rows},
          _cols{cols},
          _data(rows * cols, rows * cols, value)
    {
    }

    T &operator()(Rank row, Rank col)
    {
        return _data[row * _cols + col];
    }

    T const &operator()(Rank row, Rank col) const
    {
        return _data[row * _cols + col];
    }

    Matrix<T> matmulIJK(Matrix<T> const &rhs) const
    {
        checkMul(rhs);

        Matrix<T> result{_rows, rhs._cols, T{}};

        for (Rank i{0}; i < _rows; ++i)
        {
            for (Rank j{0}; j < rhs._cols; ++j)
            {
                T sum{0};

                for (Rank k{0}; k < _cols; ++k)
                    sum += _data[i * _cols + k] * rhs._data[k * rhs._cols + j];

                result._data[i * rhs._cols + j] = sum;
            }
        }

        return result;
    }

    Matrix<T> matmulIKJ(Matrix<T> const &rhs) const
    {
        checkMul(rhs);

        Matrix<T> result{_rows, rhs._cols, T{}};

        for (Rank i{0}; i < _rows; ++i)
        {
            for (Rank k{0}; k < _cols; ++k)
            {
                T const a{_data[i * _cols + k]};

                for (Rank j{0}; j < rhs._cols; ++j)
                    result._data[i * rhs._cols + j] +=
                        a * rhs._data[k * rhs._cols + j];
            }
        }

        return result;
    }

    Matrix<T> matmulBlocked(Matrix<T> const &rhs) const
    {
        checkMul(rhs);

        Rank I_bSize{64};
        Rank K_bSize{64};
        Rank J_bSize{128};

        Matrix<T> result{_rows, rhs._cols, T{}};

        for (Rank ii{0}; ii < _rows; ii += I_bSize)
        {
            for (Rank kk{0}; kk < _cols; kk += K_bSize)
            {
                for (Rank jj{0}; jj < rhs._cols; jj += J_bSize)
                {
                    Rank const iEnd{min(ii + I_bSize, _rows)};
                    Rank const kEnd{min(kk + K_bSize, _cols)};
                    Rank const jEnd{min(jj + J_bSize, rhs._cols)};

                    for (Rank i{ii}; i < iEnd; ++i)
                    {
                        for (Rank k{kk}; k < kEnd; ++k)
                        {
                            T const a{_data[i * _cols + k]};

                            for (Rank j{jj}; j < jEnd; ++j)
                                result._data[i * rhs._cols + j] +=
                                    a * rhs._data[k * rhs._cols + j];
                        }
                    }
                }
            }
        }

        return result;
    }

#if defined(__AVX__) && defined(__FMA__)
    Matrix<T> matmulSIMD(Matrix<T> const &rhs) const
    {
        checkMul(rhs);

        Rank I_bSize{64};
        Rank K_bSize{64};
        Rank J_bSize{128};

        Matrix<T> result{_rows, rhs._cols, T{}};

        for (Rank ii{0}; ii < _rows; ii += I_bSize)
        {
            for (Rank kk{0}; kk < _cols; kk += K_bSize)
            {
                for (Rank jj{0}; jj < rhs._cols; jj += J_bSize)
                {
                    Rank const iEnd{min(ii + I_bSize, _rows)};
                    Rank const kEnd{min(kk + K_bSize, _cols)};
                    Rank const jEnd{min(jj + J_bSize, rhs._cols)};

                    for (Rank i{ii}; i < iEnd; ++i)
                    {
                        for (Rank k{kk}; k < kEnd; ++k)
                        {
                            T const a{_data[i * _cols + k]};
                            T const *rhsRow{&rhs._data[k * rhs._cols]};
                            T *resultRow{&result._data[i * rhs._cols]};
                            avxSIMD(a, rhsRow, resultRow, jj, jEnd);
                        }
                    }
                }
            }
        }

        return result;
    }

    Matrix<T> matmulMicroKernelSIMD(Matrix<T> const &rhs) const
    {
        checkMul(rhs);

        Rank I_bSize{64};
        Rank K_bSize{64};
        Rank J_bSize{128};

        Matrix<T> result{_rows, rhs._cols, T{}};

        Rank const microRows{4};
        Rank const microCols{std::is_same<T, float>::value ? 16 : 8};

        for (Rank ii{0}; ii < _rows; ii += I_bSize)
        {
            for (Rank kk{0}; kk < _cols; kk += K_bSize)
            {
                for (Rank jj{0}; jj < rhs._cols; jj += J_bSize)
                {
                    Rank const iEnd{min(ii + I_bSize, _rows)};
                    Rank const kEnd{min(kk + K_bSize, _cols)};
                    Rank const jEnd{min(jj + J_bSize, rhs._cols)};

                    Rank i{ii};

                    for (; i + microRows <= iEnd; i += microRows)
                    {
                        Rank j{jj};

                        for (; j + microCols <= jEnd; j += microCols)
                            avxMicroKernel(rhs, result, i, kk, kEnd, j);

                        if (j < jEnd)
                        {
                            for (Rank row{i}; row < i + microRows; ++row)
                            {
                                T *resultRow{&result._data[row * rhs._cols]};

                                for (Rank k{kk}; k < kEnd; ++k)
                                {
                                    T const a{_data[row * _cols + k]};
                                    T const *rhsRow{&rhs._data[k * rhs._cols]};
                                    avxSIMD(a, rhsRow, resultRow, j, jEnd);
                                }
                            }
                        }
                    }

                    for (; i < iEnd; ++i)
                    {
                        T *resultRow{&result._data[i * rhs._cols]};

                        for (Rank k{kk}; k < kEnd; ++k)
                        {
                            T const a{_data[i * _cols + k]};
                            T const *rhsRow{&rhs._data[k * rhs._cols]};
                            avxSIMD(a, rhsRow, resultRow, jj, jEnd);
                        }
                    }
                }
            }
        }

        return result;
    }

    Matrix<T> matmulOpenMP(Matrix<T> const &rhs) const
    {
        checkMul(rhs);

        Rank I_bSize{64};
        Rank K_bSize{64};
        Rank J_bSize{128};

        Matrix<T> result{_rows, rhs._cols, T{}};

        Rank const microRows{4};
        Rank const microCols{std::is_same<T, float>::value ? 16 : 8};

#ifdef _OPENMP
#pragma omp parallel for collapse(1) schedule(static)
#endif
        for (Rank ii{0}; ii < _rows; ii += I_bSize)
        {
            for (Rank kk{0}; kk < _cols; kk += K_bSize)
            {
                for (Rank jj{0}; jj < rhs._cols; jj += J_bSize)
                {
                    Rank const iEnd{min(ii + I_bSize, _rows)};
                    Rank const kEnd{min(kk + K_bSize, _cols)};
                    Rank const jEnd{min(jj + J_bSize, rhs._cols)};

                    Rank i{ii};

                    for (; i + microRows <= iEnd; i += microRows)
                    {
                        Rank j{jj};

                        for (; j + microCols <= jEnd; j += microCols)
                            avxMicroKernel(rhs, result, i, kk, kEnd, j);

                        if (j < jEnd)
                        {
                            for (Rank row{i}; row < i + microRows; ++row)
                            {
                                T *resultRow{&result._data[row * rhs._cols]};

                                for (Rank k{kk}; k < kEnd; ++k)
                                {
                                    T const a{_data[row * _cols + k]};
                                    T const *rhsRow{&rhs._data[k * rhs._cols]};
                                    avxSIMD(a, rhsRow, resultRow, j, jEnd);
                                }
                            }
                        }
                    }

                    for (; i < iEnd; ++i)
                    {
                        T *resultRow{&result._data[i * rhs._cols]};

                        for (Rank k{kk}; k < kEnd; ++k)
                        {
                            T const a{_data[i * _cols + k]};
                            T const *rhsRow{&rhs._data[k * rhs._cols]};
                            avxSIMD(a, rhsRow, resultRow, jj, jEnd);
                        }
                    }
                }
            }
        }

        return result;
    }
#endif

    Matrix<T> matmul(Matrix<T> const &rhs) const
    {
        return matmulSIMD(rhs);
    }

    Matrix<T> operator*(Matrix<T> const &rhs) const
    {
        return matmul(rhs);
    }
};
