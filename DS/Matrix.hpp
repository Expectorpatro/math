#pragma once

#include "Vector.hpp"

#include <stdexcept>
#include <type_traits>

#if defined(__AVX__)
#include <immintrin.h>
#endif

constexpr Rank I_bSize{64};
constexpr Rank K_bSize{64};
constexpr Rank J_bSize{128};

template <typename T>
class Matrix
{
private:
    Rank _rows{};
    Rank _cols{};
    Vector<T> _data{};

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

    void avxMicroKernel(T const *A,
                        T const *B,
                        T *C,
                        Rank iBegin,
                        Rank kBegin,
                        Rank kEnd,
                        Rank jBegin,
                        Rank K,
                        Rank N) const
    {
        if constexpr (std::is_same<T, float>::value)
        {
            __m256 c00{_mm256_loadu_ps(C + iBegin * N + jBegin)};
            __m256 c01{_mm256_loadu_ps(C + iBegin * N + jBegin + 8)};
            __m256 c10{_mm256_loadu_ps(C + (iBegin + 1) * N + jBegin)};
            __m256 c11{_mm256_loadu_ps(C + (iBegin + 1) * N + jBegin + 8)};
            __m256 c20{_mm256_loadu_ps(C + (iBegin + 2) * N + jBegin)};
            __m256 c21{_mm256_loadu_ps(C + (iBegin + 2) * N + jBegin + 8)};
            __m256 c30{_mm256_loadu_ps(C + (iBegin + 3) * N + jBegin)};
            __m256 c31{_mm256_loadu_ps(C + (iBegin + 3) * N + jBegin + 8)};

            for (Rank k{kBegin}; k < kEnd; ++k)
            {
                __m256 b0{_mm256_loadu_ps(B + k * N + jBegin)};
                __m256 b1{_mm256_loadu_ps(B + k * N + jBegin + 8)};

                __m256 a{_mm256_set1_ps(A[iBegin * K + k])};
                c00 = _mm256_fmadd_ps(a, b0, c00);
                c01 = _mm256_fmadd_ps(a, b1, c01);

                a = _mm256_set1_ps(A[(iBegin + 1) * K + k]);
                c10 = _mm256_fmadd_ps(a, b0, c10);
                c11 = _mm256_fmadd_ps(a, b1, c11);

                a = _mm256_set1_ps(A[(iBegin + 2) * K + k]);
                c20 = _mm256_fmadd_ps(a, b0, c20);
                c21 = _mm256_fmadd_ps(a, b1, c21);

                a = _mm256_set1_ps(A[(iBegin + 3) * K + k]);
                c30 = _mm256_fmadd_ps(a, b0, c30);
                c31 = _mm256_fmadd_ps(a, b1, c31);
            }

            _mm256_storeu_ps(C + iBegin * N + jBegin, c00);
            _mm256_storeu_ps(C + iBegin * N + jBegin + 8, c01);
            _mm256_storeu_ps(C + (iBegin + 1) * N + jBegin, c10);
            _mm256_storeu_ps(C + (iBegin + 1) * N + jBegin + 8, c11);
            _mm256_storeu_ps(C + (iBegin + 2) * N + jBegin, c20);
            _mm256_storeu_ps(C + (iBegin + 2) * N + jBegin + 8, c21);
            _mm256_storeu_ps(C + (iBegin + 3) * N + jBegin, c30);
            _mm256_storeu_ps(C + (iBegin + 3) * N + jBegin + 8, c31);
        }
        else if constexpr (std::is_same<T, double>::value)
        {
            __m256d c00{_mm256_loadu_pd(C + iBegin * N + jBegin)};
            __m256d c01{_mm256_loadu_pd(C + iBegin * N + jBegin + 4)};
            __m256d c10{_mm256_loadu_pd(C + (iBegin + 1) * N + jBegin)};
            __m256d c11{_mm256_loadu_pd(C + (iBegin + 1) * N + jBegin + 4)};
            __m256d c20{_mm256_loadu_pd(C + (iBegin + 2) * N + jBegin)};
            __m256d c21{_mm256_loadu_pd(C + (iBegin + 2) * N + jBegin + 4)};
            __m256d c30{_mm256_loadu_pd(C + (iBegin + 3) * N + jBegin)};
            __m256d c31{_mm256_loadu_pd(C + (iBegin + 3) * N + jBegin + 4)};

            for (Rank k{kBegin}; k < kEnd; ++k)
            {
                __m256d b0{_mm256_loadu_pd(B + k * N + jBegin)};
                __m256d b1{_mm256_loadu_pd(B + k * N + jBegin + 4)};

                __m256d a{_mm256_set1_pd(A[iBegin * K + k])};
                c00 = _mm256_fmadd_pd(a, b0, c00);
                c01 = _mm256_fmadd_pd(a, b1, c01);

                a = _mm256_set1_pd(A[(iBegin + 1) * K + k]);
                c10 = _mm256_fmadd_pd(a, b0, c10);
                c11 = _mm256_fmadd_pd(a, b1, c11);

                a = _mm256_set1_pd(A[(iBegin + 2) * K + k]);
                c20 = _mm256_fmadd_pd(a, b0, c20);
                c21 = _mm256_fmadd_pd(a, b1, c21);

                a = _mm256_set1_pd(A[(iBegin + 3) * K + k]);
                c30 = _mm256_fmadd_pd(a, b0, c30);
                c31 = _mm256_fmadd_pd(a, b1, c31);
            }

            _mm256_storeu_pd(C + iBegin * N + jBegin, c00);
            _mm256_storeu_pd(C + iBegin * N + jBegin + 4, c01);
            _mm256_storeu_pd(C + (iBegin + 1) * N + jBegin, c10);
            _mm256_storeu_pd(C + (iBegin + 1) * N + jBegin + 4, c11);
            _mm256_storeu_pd(C + (iBegin + 2) * N + jBegin, c20);
            _mm256_storeu_pd(C + (iBegin + 2) * N + jBegin + 4, c21);
            _mm256_storeu_pd(C + (iBegin + 3) * N + jBegin, c30);
            _mm256_storeu_pd(C + (iBegin + 3) * N + jBegin + 4, c31);
        }
    }

    Vector<T> packA(Rank iBegin,
                    Rank iEnd,
                    Rank kBegin,
                    Rank kEnd,
                    Rank microRows,
                    T *A,
                    Rank K) const
    {
        Rank const rowCount{iEnd - iBegin};
        Rank const kCount{kEnd - kBegin};

        Rank const rowPanelCount{(rowCount + microRows - 1) / microRows};
        Rank const packedSize{rowPanelCount * microRows * kCount};
        Vector<T> packedA{packedSize, packedSize, T{}};

        Rank dst{0};
        for (Rank i{iBegin}; i < iEnd; i += microRows)
        {
            for (Rank k{kBegin}; k < kEnd; ++k)
            {
                for (Rank row{0}; row < microRows; ++row)
                {
                    Rank const srcRow{i + row};

                    if (srcRow < iEnd)
                    {
                        packedA[dst] = A[srcRow * K + k];
                    }
                    dst += 1;
                }
            }
        }

        return packedA;
    }

    Vector<T> packB(Rank kBegin,
                    Rank kEnd,
                    Rank jBegin,
                    Rank jEnd,
                    Rank microCols,
                    T *B,
                    Rank N) const
    {
        Rank const colCount{jEnd - jBegin};
        Rank const kCount{kEnd - kBegin};

        Rank const colPanelCount{(colCount + microCols - 1) / microCols};
        Rank const packedSize{colPanelCount * microCols * kCount};
        Vector<T> packedB{packedSize, packedSize, T{}};

        Rank dst{0};

        for (Rank k{kBegin}; k < kEnd; ++k)
        {
            for (Rank j{jBegin}; j < jEnd; j += microCols)
            {
                for (Rank col{0}; col < microCols; ++col)
                {
                    Rank const srcCol{j + col};
                    if (srcCol < jEnd)
                    {
                        packedB[dst] = B[k * N + srcCol];
                    }
                    dst += 1;
                }
            }
        }

        return packedB;
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

        Rank const M{_rows};
        Rank const K{_cols};
        Rank const N{rhs._cols};
        Matrix<T> result{M, N, T{}};

        T const *A{&_data[0]};
        T const *B{&rhs._data[0]};
        T *C{&result._data[0]};

        for (Rank i{0}; i < M; ++i)
        {
            T const *aRow{A + i * K};
            T *cRow{C + i * N};

            for (Rank j{0}; j < N; ++j)
            {
                T sum{};

                T const *bPtr{B + j};

                for (Rank k{0}; k < K; ++k)
                {
                    sum += aRow[k] * (*bPtr);
                    bPtr += N;
                }

                cRow[j] = sum;
            }
        }

        return result;
    }

    Matrix<T> matmulIKJ(Matrix<T> const &rhs) const
    {
        checkMul(rhs);

        Rank const M{_rows};
        Rank const K{_cols};
        Rank const N{rhs._cols};
        Matrix<T> result{M, N, T{}};

        T const *A{&_data[0]};
        T const *B{&rhs._data[0]};
        T *C{&result._data[0]};

        for (Rank i{0}; i < M; ++i)
        {
            T const *aRow{A + i * K};
            T *cRow{C + i * N};

            for (Rank k{0}; k < K; ++k)
            {
                T const a{aRow[k]};
                T const *bRow{B + k * N};

                for (Rank j{0}; j < N; ++j)
                {
                    cRow[j] += a * bRow[j];
                }
            }
        }

        return result;
    }

    Matrix<T> matmulBlocked(Matrix<T> const &rhs) const
    {
        checkMul(rhs);

        Rank const M{_rows};
        Rank const K{_cols};
        Rank const N{rhs._cols};

        Matrix<T> result{M, N, T{}};

        T const *A{&_data[0]};
        T const *B{&rhs._data[0]};
        T *C{&result._data[0]};

        for (Rank ii{0}; ii < M; ii += I_bSize)
        {
            Rank const iEnd{std::min(ii + I_bSize, M)};

            for (Rank kk{0}; kk < K; kk += K_bSize)
            {
                Rank const kEnd{std::min(kk + K_bSize, K)};

                for (Rank jj{0}; jj < N; jj += J_bSize)
                {
                    Rank const jEnd{std::min(jj + J_bSize, N)};

                    for (Rank i{ii}; i < iEnd; ++i)
                    {
                        T const *aRow{A + i * K};
                        T *cRow{C + i * N};

                        for (Rank k{kk}; k < kEnd; ++k)
                        {
                            T const a{aRow[k]};
                            T const *bRow{B + k * N};

                            for (Rank j{jj}; j < jEnd; ++j)
                            {
                                cRow[j] += a * bRow[j];
                            }
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

        Rank const M{_rows};
        Rank const K{_cols};
        Rank const N{rhs._cols};
        Matrix<T> result{M, N, T{}};

        T const *A{&_data[0]};
        T const *B{&rhs._data[0]};
        T *C{&result._data[0]};

        for (Rank ii{0}; ii < M; ii += I_bSize)
        {
            Rank const iEnd{std::min(ii + I_bSize, M)};
            for (Rank kk{0}; kk < K; kk += K_bSize)
            {
                Rank const kEnd{std::min(kk + K_bSize, K)};
                for (Rank jj{0}; jj < N; jj += J_bSize)
                {
                    Rank const jEnd{std::min(jj + J_bSize, N)};

                    for (Rank i{ii}; i < iEnd; ++i)
                    {
                        T *resultRow{C + i * N};
                        for (Rank k{kk}; k < kEnd; ++k)
                        {
                            T const a{A[i * K + k]};
                            T const *rhsRow{B + k * N};
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

        Rank const M{_rows};
        Rank const K{_cols};
        Rank const N{rhs._cols};
        Matrix<T> result{M, N, T{}};

        T const *A{&_data[0]};
        T const *B{&rhs._data[0]};
        T *C{&result._data[0]};

        Rank const microRows{4};
        Rank const microCols{std::is_same<T, float>::value ? 16 : 8};

        for (Rank ii{0}; ii < M; ii += I_bSize)
        {
            Rank const iEnd{std::min(ii + I_bSize, M)};

            for (Rank kk{0}; kk < K; kk += K_bSize)
            {
                Rank const kEnd{std::min(kk + K_bSize, K)};

                for (Rank jj{0}; jj < N; jj += J_bSize)
                {
                    Rank const jEnd{std::min(jj + J_bSize, N)};

                    Rank i{ii};

                    for (; i + microRows <= iEnd; i += microRows)
                    {
                        Rank j{jj};

                        for (; j + microCols <= jEnd; j += microCols)
                        {
                            avxMicroKernel(A, B, C, i, kk, kEnd, j, K, N);
                        }

                        if (j < jEnd)
                        {
                            for (Rank row{i}; row < i + microRows; ++row)
                            {
                                T *resultRow{C + row * N};

                                for (Rank k{kk}; k < kEnd; ++k)
                                {
                                    T const a{A[row * K + k]};
                                    T const *rhsRow{B + k * N};

                                    avxSIMD(a, rhsRow, resultRow, j, jEnd);
                                }
                            }
                        }
                    }

                    for (; i < iEnd; ++i)
                    {
                        T *resultRow{C + i * N};

                        for (Rank k{kk}; k < kEnd; ++k)
                        {
                            T const a{A[i * K + k]};
                            T const *rhsRow{B + k * N};

                            avxSIMD(a, rhsRow, resultRow, jj, jEnd);
                        }
                    }
                }
            }
        }

        return result;
    }

    Matrix<T> matmulPacking(Matrix<T> const &rhs) const
    {
        checkMul(rhs);

        Rank const M{_rows};
        Rank const K{_cols};
        Rank const N{rhs._cols};
        Matrix<T> result{M, N, T{}};

        T const *A{&_data[0]};
        T const *B{&rhs._data[0]};
        T *C{&result._data[0]};

        Rank const microRows{4};
        Rank const microCols{std::is_same<T, float>::value ? 16 : 8};

        for (Rank ii{0}; ii < M; ii += I_bSize)
        {
            Rank const iEnd{std::min(ii + I_bSize, M)};

            for (Rank kk{0}; kk < K; kk += K_bSize)
            {
                Rank const kEnd{std::min(kk + K_bSize, K)};

                Vector<T> packedA{packA(ii, iEnd, kk, kEnd, microRows, A, K)};
                T const *packedAPtr{packedA._elem};

                for (Rank jj{0}; jj < N; jj += J_bSize)
                {
                    Rank const jEnd{std::min(jj + J_bSize, N)};
                    Vector<T> packedB{packB(kk, kEnd, jj, jEnd, microCols, A, K)};
                    T const *packedBPtr{packedB._elem};
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
