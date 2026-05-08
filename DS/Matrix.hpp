#pragma once

#include "Vector.hpp"

#include <stdexcept>
#include <type_traits>
#include <algorithm>

#if defined(__AVX__) && defined(__FMA__)
#include <immintrin.h>
#endif

constexpr int I_bSize{64};
constexpr int K_bSize{64};
constexpr int J_bSize{128};

template <typename T>
struct AvxTraits
{
    using Vec = std::conditional_t<
        std::is_same_v<T, float>,
        __m256,
        __m256d>;

    static constexpr int lanes = std::is_same_v<T, float> ? 8 : 4;

    static inline Vec load(T const *ptr)
    {
        if constexpr (std::is_same_v<T, float>)
        {
            return _mm256_loadu_ps(ptr);
        }
        else
        {
            return _mm256_loadu_pd(ptr);
        }
    }

    static inline void store(T *ptr, Vec value)
    {
        if constexpr (std::is_same_v<T, float>)
        {
            _mm256_storeu_ps(ptr, value);
        }
        else
        {
            _mm256_storeu_pd(ptr, value);
        }
    }

    static inline Vec set1(T value)
    {
        if constexpr (std::is_same_v<T, float>)
        {
            return _mm256_set1_ps(value);
        }
        else
        {
            return _mm256_set1_pd(value);
        }
    }

    static inline Vec fmadd(Vec a, Vec b, Vec c)
    {
        if constexpr (std::is_same_v<T, float>)
        {
            return _mm256_fmadd_ps(a, b, c);
        }
        else
        {
            return _mm256_fmadd_pd(a, b, c);
        }
    }
};

template <typename T>
class Matrix
{
private:
    int _rows{};
    int _cols{};
    Vector<T> _data{};

    void checkMul(Matrix<T> const &rhs) const
    {
        if (_cols != rhs._rows)
            throw std::invalid_argument{"Matrix dimensions do not match"};
    }

#if defined(__AVX__) && defined(__FMA__)
    using Simd = AvxTraits<T>;
    using Vec = typename Simd::Vec;
    static constexpr int microRows{4};
    static constexpr int numColSIMD{2};
    static constexpr int numAccumulators{microRows * numColSIMD};

    static void avxSIMD(
        T const &a,
        T const *rhsRow,
        T *resultRow,
        int begin,
        int end)
    {
        Vec va{Simd::set1(a)};

        int j{begin};

        for (; j + Simd::lanes <= end; j += Simd::lanes)
        {
            Vec vb{Simd::load(rhsRow + j)};
            Vec vc{Simd::load(resultRow + j)};

            vc = Simd::fmadd(va, vb, vc);

            Simd::store(resultRow + j, vc);
        }

        for (; j < end; ++j)
        {
            resultRow[j] += a * rhsRow[j];
        }
    }

    void avxMicroKernel(T const *A,
                        T const *B,
                        T *C,
                        int iBegin,
                        int kBegin,
                        int kEnd,
                        int jBegin,
                        int K,
                        int N) const
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

            for (int k{kBegin}; k < kEnd; ++k)
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

            for (int k{kBegin}; k < kEnd; ++k)
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

    template <int numC>
    inline void loadCFloatUnrolled(
        float *C,
        std::array<__m256, numAccumulators> &c,
        int iBegin,
        int jBegin,
        int N)
    {
        if constexpr (numC < numAccumulators)
        {
            constexpr int rowBlock{numC / numColSIMD};
            constexpr int colBlock{numC % numColSIMD};

            c[numC] = _mm256_loadu_ps(C + (iBegin + rowBlock) * N + jBegin + colBlock * 8);

            loadCFloatUnrolled<numC + 1>(C, c, iBegin, jBegin, N);
        }
    }

    template <int numC>
    inline void storeCFloatUnrolled(
        float *C,
        std::array<__m256, numAccumulators> const &c,
        int iBegin,
        int jBegin,
        int N)
    {
        if constexpr (numC < numAccumulators)
        {
            constexpr int rowBlock{numC / numColSIMD};
            constexpr int colBlock{numC % numColSIMD};

            _mm256_storeu_ps(
                C + (iBegin + rowBlock) * N + jBegin + colBlock * 8,
                c[numC]);

            storeCFloatUnrolled<numC + 1>(C, c, iBegin, jBegin, N);
        }
    }

    template <int numB>
    inline void loadBFloatUnrolled(
        float const *B,
        std::array<__m256, numColSIMD> &b,
        int k,
        int jBegin,
        int N)
    {
        if constexpr (numB < numColSIMD)
        {

            b[numB] = _mm256_loadu_ps(B + k * N + jBegin + numB * 8);

            loadBFloatUnrolled<numB + 1>(B, b, k, jBegin, N);
        }
    }

    template <int rowC, int numB>
    inline void updateFloatColsUnrolled(
        __m256 a,
        std::array<__m256, numColSIMD> const &b,
        std::array<__m256, numAccumulators> &c) noexcept
    {
        if constexpr (numB < numColSIMD)
        {
            constexpr int q{rowC * numColSIMD + numB};

            c[q] = _mm256_fmadd_ps(a, b[numB], c[q]);

            updateFloatColsUnrolled<rowC, numB + 1>(a, b, c);
        }
    }

    template <int rowC>
    inline void updateFloatRowsUnrolled(
        float const *A,
        std::array<__m256, numColSIMD> const &b,
        std::array<__m256, numAccumulators> &c,
        int iBegin,
        int k,
        int K) noexcept
    {
        if constexpr (rowC < microRows)
        {
            __m256 a{_mm256_set1_ps(A[(iBegin + rowC) * K + k])};

            updateFloatColsUnrolled<rowC, 0>(a, b, c);

            updateFloatRowsUnrolled<rowC + 1>(A, b, c, iBegin, k, K);
        }
    }

    Vector<T> packA(int iBegin,
                    int iEnd,
                    int kBegin,
                    int kEnd,
                    int microRows,
                    T *A,
                    int K) const
    {
        int const rowCount{iEnd - iBegin};
        int const kCount{kEnd - kBegin};

        int const rowPanelCount{(rowCount + microRows - 1) / microRows};
        int const packedSize{rowPanelCount * microRows * kCount};
        Vector<T> packedA{packedSize, packedSize, T{}};

        int dst{0};
        for (int i{iBegin}; i < iEnd; i += microRows)
        {
            for (int k{kBegin}; k < kEnd; ++k)
            {
                for (int row{0}; row < microRows; ++row)
                {
                    int const srcRow{i + row};

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

    Vector<T> packB(int kBegin,
                    int kEnd,
                    int jBegin,
                    int jEnd,
                    int microCols,
                    T *B,
                    int N) const
    {
        int const colCount{jEnd - jBegin};
        int const kCount{kEnd - kBegin};

        int const colPanelCount{(colCount + microCols - 1) / microCols};
        int const packedSize{colPanelCount * microCols * kCount};
        Vector<T> packedB{packedSize, packedSize, T{}};

        int dst{0};

        for (int k{kBegin}; k < kEnd; ++k)
        {
            for (int j{jBegin}; j < jEnd; j += microCols)
            {
                for (int col{0}; col < microCols; ++col)
                {
                    int const srcCol{j + col};
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

    void avxPackingKernel(T const *packedA,
                          T const *packedB,
                          T *C,
                          int iBegin,
                          int jBegin,
                          int kCount,
                          int packedBStride,
                          int N) const
    {
        int const microRows{4};

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

            for (int k{0}; k < kCount; ++k)
            {
                T const *aPtr{packedA + k * microRows};
                T const *bPtr{packedB + k * packedBStride};
                __m256 b0{_mm256_loadu_ps(bPtr)};
                __m256 b1{_mm256_loadu_ps(bPtr + 8)};

                __m256 a{_mm256_set1_ps(aPtr[0])};
                c00 = _mm256_fmadd_ps(a, b0, c00);
                c01 = _mm256_fmadd_ps(a, b1, c01);

                a = _mm256_set1_ps(aPtr[1]);
                c10 = _mm256_fmadd_ps(a, b0, c10);
                c11 = _mm256_fmadd_ps(a, b1, c11);

                a = _mm256_set1_ps(aPtr[2]);
                c20 = _mm256_fmadd_ps(a, b0, c20);
                c21 = _mm256_fmadd_ps(a, b1, c21);

                a = _mm256_set1_ps(aPtr[3]);
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

            for (int k{0}; k < kCount; ++k)
            {
                T const *aPtr{packedA + k * microRows};
                T const *bPtr{packedB + k * packedBStride};
                __m256d b0{_mm256_loadu_pd(bPtr)};
                __m256d b1{_mm256_loadu_pd(bPtr + 4)};

                __m256d a{_mm256_set1_pd(aPtr[0])};
                c00 = _mm256_fmadd_pd(a, b0, c00);
                c01 = _mm256_fmadd_pd(a, b1, c01);

                a = _mm256_set1_pd(aPtr[1]);
                c10 = _mm256_fmadd_pd(a, b0, c10);
                c11 = _mm256_fmadd_pd(a, b1, c11);

                a = _mm256_set1_pd(aPtr[2]);
                c20 = _mm256_fmadd_pd(a, b0, c20);
                c21 = _mm256_fmadd_pd(a, b1, c21);

                a = _mm256_set1_pd(aPtr[3]);
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
#endif

public:
    Matrix(int rows = 0,
           int cols = 0,
           T const &value = T{})
        : _rows{rows},
          _cols{cols},
          _data(rows * cols, rows * cols, value)
    {
    }

    T &operator()(int row, int col)
    {
        return _data[row * _cols + col];
    }

    T const &operator()(int row, int col) const
    {
        return _data[row * _cols + col];
    }

    Matrix<T> matmulIJK(Matrix<T> const &rhs) const
    {
        checkMul(rhs);

        int const M{_rows};
        int const K{_cols};
        int const N{rhs._cols};
        Matrix<T> result{M, N, T{}};

        T const *A{&_data[0]};
        T const *B{&rhs._data[0]};
        T *C{&result._data[0]};

        for (int i{0}; i < M; ++i)
        {
            T const *aRow{A + i * K};
            T *cRow{C + i * N};

            for (int j{0}; j < N; ++j)
            {
                T sum{};

                T const *bPtr{B + j};

                for (int k{0}; k < K; ++k)
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

        int const M{_rows};
        int const K{_cols};
        int const N{rhs._cols};
        Matrix<T> result{M, N, T{}};

        T const *A{&_data[0]};
        T const *B{&rhs._data[0]};
        T *C{&result._data[0]};

        for (int i{0}; i < M; ++i)
        {
            T const *aRow{A + i * K};
            T *cRow{C + i * N};

            for (int k{0}; k < K; ++k)
            {
                T const a{aRow[k]};
                T const *bRow{B + k * N};

                for (int j{0}; j < N; ++j)
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

        int const M{_rows};
        int const K{_cols};
        int const N{rhs._cols};
        Matrix<T> result{M, N, T{}};

        T const *A{&_data[0]};
        T const *B{&rhs._data[0]};
        T *C{&result._data[0]};

        for (int ii{0}; ii < M; ii += I_bSize)
        {
            int const iEnd{std::min(ii + I_bSize, M)};

            for (int kk{0}; kk < K; kk += K_bSize)
            {
                int const kEnd{std::min(kk + K_bSize, K)};

                for (int jj{0}; jj < N; jj += J_bSize)
                {
                    int const jEnd{std::min(jj + J_bSize, N)};

                    for (int i{ii}; i < iEnd; ++i)
                    {
                        T const *aRow{A + i * K};
                        T *cRow{C + i * N};

                        for (int k{kk}; k < kEnd; ++k)
                        {
                            T const a{aRow[k]};
                            T const *bRow{B + k * N};

                            for (int j{jj}; j < jEnd; ++j)
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

        int const M{_rows};
        int const K{_cols};
        int const N{rhs._cols};
        Matrix<T> result{M, N, T{}};

        T const *A{&_data[0]};
        T const *B{&rhs._data[0]};
        T *C{&result._data[0]};

        for (int ii{0}; ii < M; ii += I_bSize)
        {
            int const iEnd{std::min(ii + I_bSize, M)};
            for (int kk{0}; kk < K; kk += K_bSize)
            {
                int const kEnd{std::min(kk + K_bSize, K)};
                for (int jj{0}; jj < N; jj += J_bSize)
                {
                    int const jEnd{std::min(jj + J_bSize, N)};

                    for (int i{ii}; i < iEnd; ++i)
                    {
                        T *resultRow{C + i * N};
                        for (int k{kk}; k < kEnd; ++k)
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

        int const M{_rows};
        int const K{_cols};
        int const N{rhs._cols};
        Matrix<T> result{M, N, T{}};

        T const *A{&_data[0]};
        T const *B{&rhs._data[0]};
        T *C{&result._data[0]};

        int const microCols{SIMD::lanes * numColSIMD};

        for (int ii{0}; ii < M; ii += I_bSize)
        {
            int const iEnd{std::min(ii + I_bSize, M)};

            for (int kk{0}; kk < K; kk += K_bSize)
            {
                int const kEnd{std::min(kk + K_bSize, K)};

                for (int jj{0}; jj < N; jj += J_bSize)
                {
                    int const jEnd{std::min(jj + J_bSize, N)};

                    int const iFullEnd{iEnd - ((iEnd - ii) % microRows)};
                    int const jFullEnd{jEnd - ((jEnd - jj) % microCols)};
                    bool const hasRightTail{jFullEnd < jEnd};

                    if (!hasRightTail)
                    {
                        for (int i{ii}; i < iFullEnd; i += microRows)
                        {
                            for (int j{jj}; j < jFullEnd; j += microCols)
                            {
                                avxMicroKernel(A, B, C, i, kk, kEnd, j, K, N);
                            }
                        }
                    }
                    else
                    {
                        for (int i{ii}; i < iFullEnd; i += microRows)
                        {
                            for (int j{jj}; j < jFullEnd; j += microCols)
                            {
                                avxMicroKernel(A, B, C, i, kk, kEnd, j, K, N);
                            }

                            for (int row{i}; row < i + microRows; ++row)
                            {
                                T *resultRow{C + row * N};

                                for (int k{kk}; k < kEnd; ++k)
                                {
                                    T const a{A[row * K + k]};
                                    T const *rhsRow{B + k * N};

                                    avxSIMD(a, rhsRow, resultRow, jFullEnd, jEnd);
                                }
                            }
                        }
                    }

                    for (int i{iFullEnd}; i < iEnd; ++i)
                    {
                        T *resultRow{C + i * N};

                        for (int k{kk}; k < kEnd; ++k)
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

        int const M{_rows};
        int const K{_cols};
        int const N{rhs._cols};
        Matrix<T> result{M, N, T{}};

        T const *A{&_data[0]};
        T const *B{&rhs._data[0]};
        T *C{&result._data[0]};

        int const microCols{std::is_same<T, float>::value ? 8 * numColSIMD : 4 * numColSIMD};

        for (int ii{0}; ii < M; ii += I_bSize)
        {
            int const iEnd{std::min(ii + I_bSize, M)};

            for (int kk{0}; kk < K; kk += K_bSize)
            {
                int const kEnd{std::min(kk + K_bSize, K)};

                Vector<T> packedA{packA(ii, iEnd, kk, kEnd, microRows, A, K)};
                T const *packedAPtr{&packedA[0]};

                for (int jj{0}; jj < N; jj += J_bSize)
                {
                    int const jEnd{std::min(jj + J_bSize, N)};

                    Vector<T> packedB{packB(kk, kEnd, jj, jEnd, microCols, A, K)};
                    T const *packedBPtr{&packedB[0]};

                    int const iFullEnd{iEnd - ((iEnd - ii) % microRows)};
                    int const jFullEnd{jEnd - ((jEnd - jj) % microCols)};
                    bool const hasRightTail{jFullEnd < jEnd};

                    if (!hasRightTail)
                    {
                        for (int i{ii}; i < iFullEnd; i += microRows)
                        {
                            for (int j{jj}; j < jFullEnd; j += microCols)
                            {
                                avxMicroKernel(A, B, C, i, kk, kEnd, j, K, N);
                            }
                        }
                    }
                    else
                    {
                        for (int i{ii}; i < iFullEnd; i += microRows)
                        {
                            for (int j{jj}; j < jFullEnd; j += microCols)
                            {
                                avxMicroKernel(A, B, C, i, kk, kEnd, j, K, N);
                            }

                            for (int row{i}; row < i + microRows; ++row)
                            {
                                T *resultRow{C + row * N};

                                for (int k{kk}; k < kEnd; ++k)
                                {
                                    T const a{A[row * K + k]};
                                    T const *rhsRow{B + k * N};

                                    avxSIMD(a, rhsRow, resultRow, jFullEnd, jEnd);
                                }
                            }
                        }
                    }

                    for (int i{iFullEnd}; i < iEnd; ++i)
                    {
                        T *resultRow{C + i * N};

                        for (int k{kk}; k < kEnd; ++k)
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
