#pragma once

#if defined(__AVX__) && defined(__FMA__)
#include "AvxMicroKernel.hpp"
#endif
#include "Vector.hpp"

#include <stdexcept>
#include <algorithm>

constexpr int I_bSize{64};
constexpr int K_bSize{64};
constexpr int J_bSize{128};

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
    using Kernel = AvxMicroKernel<T>;
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
                        T *CRow{C + i * N};
                        for (int k{kk}; k < kEnd; ++k)
                        {
                            T const a{A[i * K + k]};
                            T const *BRow{B + k * N};
                            Kernel::updateRow(a, BRow, CRow, jj, jEnd);
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

        for (int ii{0}; ii < M; ii += I_bSize)
        {
            int const iEnd{std::min(ii + I_bSize, M)};

            for (int kk{0}; kk < K; kk += K_bSize)
            {
                int const kEnd{std::min(kk + K_bSize, K)};

                for (int jj{0}; jj < N; jj += J_bSize)
                {
                    int const jEnd{std::min(jj + J_bSize, N)};

                    int const iFullEnd{iEnd - ((iEnd - ii) % Kernel::microRows)};
                    int const jFullEnd{jEnd - ((jEnd - jj) % Kernel::microCols)};
                    bool const hasRightTail{jFullEnd < jEnd};

                    if (!hasRightTail)
                    {
                        for (int i{ii}; i < iFullEnd; i += Kernel::microRows)
                        {
                            for (int j{jj}; j < jFullEnd; j += Kernel::microCols)
                            {
                                Kernel::run(A, B, C, i, kk, kEnd, j, K, N);
                            }
                        }
                    }
                    else
                    {
                        for (int i{ii}; i < iFullEnd; i += Kernel::microRows)
                        {
                            for (int j{jj}; j < jFullEnd; j += Kernel::microCols)
                            {
                                Kernel::run(A, B, C, i, kk, kEnd, j, K, N);
                            }

                            for (int row{i}; row < i + Kernel::microRows; ++row)
                            {
                                T *CRow{C + row * N};

                                for (int k{kk}; k < kEnd; ++k)
                                {
                                    T const a{A[row * K + k]};
                                    T const *BRow{B + k * N};

                                    Kernel::updateRow(a, BRow, CRow, jFullEnd, jEnd);
                                }
                            }
                        }
                    }

                    for (int i{iFullEnd}; i < iEnd; ++i)
                    {
                        T *CRow{C + i * N};

                        for (int k{kk}; k < kEnd; ++k)
                        {
                            T const a{A[i * K + k]};
                            T const *BRow{B + k * N};

                            Kernel::updateRow(a, BRow, CRow, jj, jEnd);
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

        for (int ii{0}; ii < M; ii += I_bSize)
        {
            int const iEnd{std::min(ii + I_bSize, M)};

            for (int kk{0}; kk < K; kk += K_bSize)
            {
                int const kEnd{std::min(kk + K_bSize, K)};

                int const kCount{kEnd - kk};
                Vector<T> packedA{Kernel::packA(A, ii, iEnd, kk, kEnd, K)};
                T const *packedAPtr{&packedA[0]};

                for (int jj{0}; jj < N; jj += J_bSize)
                {
                    int const jEnd{std::min(jj + J_bSize, N)};

                    Vector<T> packedB{Kernel::packB(B, kk, kEnd, jj, jEnd, N)};
                    T const *packedBPtr{&packedB[0]};
                    int const packedBStride{Kernel::packedBStride(jj, jEnd)};

                    int const iFullEnd{iEnd - ((iEnd - ii) % Kernel::microRows)};
                    int const jFullEnd{jEnd - ((jEnd - jj) % Kernel::microCols)};
                    bool const hasRightTail{jFullEnd < jEnd};

                    if (!hasRightTail)
                    {
                        for (int i{ii}; i < iFullEnd; i += Kernel::microRows)
                        {
                            for (int j{jj}; j < jFullEnd; j += Kernel::microCols)
                            {
                                T const *packedAPanel{
                                    Kernel::packedAPanel(packedAPtr, i, ii, kCount)};
                                T const *packedBPanel{
                                    Kernel::packedBPanel(packedBPtr, j, jj)};
                                Kernel::runPacked(
                                    packedAPanel, packedBPanel, C, i, j, kCount, packedBStride, N);
                            }
                        }
                    }
                    else
                    {
                        for (int i{ii}; i < iFullEnd; i += Kernel::microRows)
                        {
                            for (int j{jj}; j < jFullEnd; j += Kernel::microCols)
                            {
                                T const *packedAPanel{
                                    Kernel::packedAPanel(packedAPtr, i, ii, kCount)};
                                T const *packedBPanel{
                                    Kernel::packedBPanel(packedBPtr, j, jj)};
                                Kernel::runPacked(
                                    packedAPanel, packedBPanel, C, i, j, kCount, packedBStride, N);
                            }

                            for (int row{i}; row < i + Kernel::microRows; ++row)
                            {
                                T *CRow{C + row * N};

                                for (int k{kk}; k < kEnd; ++k)
                                {
                                    T const a{A[row * K + k]};
                                    T const *BRow{B + k * N};

                                    Kernel::updateRow(a, BRow, CRow, jFullEnd, jEnd);
                                }
                            }
                        }
                    }

                    for (int i{iFullEnd}; i < iEnd; ++i)
                    {
                        T *CRow{C + i * N};

                        for (int k{kk}; k < kEnd; ++k)
                        {
                            T const a{A[i * K + k]};
                            T const *BRow{B + k * N};

                            Kernel::updateRow(a, BRow, CRow, jj, jEnd);
                        }
                    }
                }
            }
        }

        return result;
    }
#endif
};
