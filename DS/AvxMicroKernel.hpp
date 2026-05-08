#pragma once

#include "AvxTraits.hpp"
#include "Vector.hpp"

#include <array>

template <typename T>
struct AvxMicroKernel
{
    using Simd = AvxTraits<T>;
    using Vec = typename Simd::Vec;

    static constexpr int microRows{4};
    static constexpr int numColSIMD{2};
    static constexpr int numAccumulators{microRows * numColSIMD};
    static constexpr int microCols{Simd::lanes * numColSIMD};

    using Accumulators = std::array<Vec, numAccumulators>;
    using BRegisters = std::array<Vec, numColSIMD>;

    static void updateRow(T const &a,
                          T const *BRow,
                          T *CRow,
                          int jBegin,
                          int jEnd)
    {
        Vec va{Simd::set1(a)};

        int j{jBegin};

        for (; j + Simd::lanes <= jEnd; j += Simd::lanes)
        {
            Vec vb{Simd::load(BRow + j)};
            Vec vc{Simd::load(CRow + j)};

            vc = Simd::fmadd(va, vb, vc);

            Simd::store(CRow + j, vc);
        }

        for (; j < jEnd; ++j)
        {
            CRow[j] += a * BRow[j];
        }
    }

    static void run(T const *A,
                    T const *B,
                    T *C,
                    int iBegin,
                    int kBegin,
                    int kEnd,
                    int jBegin,
                    int K,
                    int N)
    {
        Accumulators c{};
        loadC<0>(C, c, iBegin, jBegin, N);

        for (int k{kBegin}; k < kEnd; ++k)
        {
            BRegisters b{};
            loadB<0>(B, b, k, jBegin, N);
            updateRows<0>(A, b, c, iBegin, k, K);
        }

        storeC<0>(C, c, iBegin, jBegin, N);
    }

    static Vector<T> packA(T const *A,
                           int iBegin,
                           int iEnd,
                           int kBegin,
                           int kEnd,
                           int K)
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

    static Vector<T> packB(T const *B,
                           int kBegin,
                           int kEnd,
                           int jBegin,
                           int jEnd,
                           int N)
    {
        int const kCount{kEnd - kBegin};

        int const packedSize{packedBStride(jBegin, jEnd) * kCount};
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

    static int packedBStride(int jBegin, int jEnd)
    {
        int const colCount{jEnd - jBegin};
        int const colPanelCount{(colCount + microCols - 1) / microCols};
        return colPanelCount * microCols;
    }

    static T const *packedAPanel(T const *packedA,
                                 int i,
                                 int iBegin,
                                 int kCount)
    {
        return packedA + ((i - iBegin) / microRows) * microRows * kCount;
    }

    static T const *packedBPanel(T const *packedB,
                                 int j,
                                 int jBegin)
    {
        return packedB + ((j - jBegin) / microCols) * microCols;
    }

    static void runPacked(T const *packedA,
                          T const *packedB,
                          T *C,
                          int iBegin,
                          int jBegin,
                          int kCount,
                          int packedBStride,
                          int N)
    {
        Accumulators c{};
        loadC<0>(C, c, iBegin, jBegin, N);

        for (int k{0}; k < kCount; ++k)
        {
            T const *aPtr{packedA + k * microRows};
            T const *bPtr{packedB + k * packedBStride};

            BRegisters b{};
            loadPackedB<0>(bPtr, b);
            updatePackedRows<0>(aPtr, b, c);
        }

        storeC<0>(C, c, iBegin, jBegin, N);
    }

private:
    template <int numC>
    static inline void loadC(T const *C,
                             Accumulators &c,
                             int iBegin,
                             int jBegin,
                             int N)
    {
        if constexpr (numC < numAccumulators)
        {
            constexpr int rowBlock{numC / numColSIMD};
            constexpr int colBlock{numC % numColSIMD};

            c[numC] = Simd::load(
                C + (iBegin + rowBlock) * N + jBegin + colBlock * Simd::lanes);

            loadC<numC + 1>(C, c, iBegin, jBegin, N);
        }
    }

    template <int numC>
    static inline void storeC(T *C,
                              Accumulators const &c,
                              int iBegin,
                              int jBegin,
                              int N)
    {
        if constexpr (numC < numAccumulators)
        {
            constexpr int rowBlock{numC / numColSIMD};
            constexpr int colBlock{numC % numColSIMD};

            Simd::store(
                C + (iBegin + rowBlock) * N + jBegin + colBlock * Simd::lanes,
                c[numC]);

            storeC<numC + 1>(C, c, iBegin, jBegin, N);
        }
    }

    template <int numB>
    static inline void loadB(T const *B,
                             BRegisters &b,
                             int k,
                             int jBegin,
                             int N)
    {
        if constexpr (numB < numColSIMD)
        {
            b[numB] = Simd::load(B + k * N + jBegin + numB * Simd::lanes);

            loadB<numB + 1>(B, b, k, jBegin, N);
        }
    }

    template <int numB>
    static inline void loadPackedB(T const *bPtr,
                                   BRegisters &b)
    {
        if constexpr (numB < numColSIMD)
        {
            b[numB] = Simd::load(bPtr + numB * Simd::lanes);

            loadPackedB<numB + 1>(bPtr, b);
        }
    }

    template <int rowC, int numB>
    static inline void updateCols(Vec a,
                                  BRegisters const &b,
                                  Accumulators &c) noexcept
    {
        if constexpr (numB < numColSIMD)
        {
            constexpr int q{rowC * numColSIMD + numB};

            c[q] = Simd::fmadd(a, b[numB], c[q]);

            updateCols<rowC, numB + 1>(a, b, c);
        }
    }

    template <int rowC>
    static inline void updateRows(T const *A,
                                  BRegisters const &b,
                                  Accumulators &c,
                                  int iBegin,
                                  int k,
                                  int K) noexcept
    {
        if constexpr (rowC < microRows)
        {
            Vec a{Simd::set1(A[(iBegin + rowC) * K + k])};

            updateCols<rowC, 0>(a, b, c);

            updateRows<rowC + 1>(A, b, c, iBegin, k, K);
        }
    }

    template <int rowC>
    static inline void updatePackedRows(T const *aPtr,
                                        BRegisters const &b,
                                        Accumulators &c) noexcept
    {
        if constexpr (rowC < microRows)
        {
            Vec a{Simd::set1(aPtr[rowC])};

            updateCols<rowC, 0>(a, b, c);

            updatePackedRows<rowC + 1>(aPtr, b, c);
        }
    }
};
