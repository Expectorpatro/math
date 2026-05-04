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

#if defined(__AVX__)
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

    Matrix<T> matmulBlocked(Matrix<T> const &rhs, Rank blockSize = 32) const
    {
        checkMul(rhs);

        Matrix<T> result{_rows, rhs._cols, T{}};

        for (Rank ii{0}; ii < _rows; ii += blockSize)
        {
            for (Rank kk{0}; kk < _cols; kk += blockSize)
            {
                for (Rank jj{0}; jj < rhs._cols; jj += blockSize)
                {
                    Rank const iEnd{min(ii + blockSize, _rows)};
                    Rank const kEnd{min(kk + blockSize, _cols)};
                    Rank const jEnd{min(jj + blockSize, rhs._cols)};

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

    Matrix<T> matmulSIMD(Matrix<T> const &rhs, Rank blockSize = 32) const
    {
        checkMul(rhs);

#if defined(__AVX__)
        if constexpr (std::is_same<T, float>::value || std::is_same<T, double>::value)
        {
            Matrix<T> result{_rows, rhs._cols, T{}};

            for (Rank ii{0}; ii < _rows; ii += blockSize)
            {
                for (Rank kk{0}; kk < _cols; kk += blockSize)
                {
                    for (Rank jj{0}; jj < rhs._cols; jj += blockSize)
                    {
                        Rank const iEnd{min(ii + blockSize, _rows)};
                        Rank const kEnd{min(kk + blockSize, _cols)};
                        Rank const jEnd{min(jj + blockSize, rhs._cols)};

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
#endif

        return matmulBlocked(rhs, blockSize);
    }

    Matrix<T> matmul(Matrix<T> const &rhs) const
    {
        return matmulSIMD(rhs);
    }

    Matrix<T> operator*(Matrix<T> const &rhs) const
    {
        return matmul(rhs);
    }
};
