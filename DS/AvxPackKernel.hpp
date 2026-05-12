#pragma once

#include "AvxMicroKernel.hpp"
#include "Vector.hpp"

template <typename T>
struct AvxPackKernel
{
    using MicroKernel = AvxMicroKernel<T>;
    using Simd = typename MicroKernel::Simd;
    using Vec = typename MicroKernel::Vec;

    static constexpr int microRows{MicroKernel::microRows};
    static constexpr int numColSIMD{MicroKernel::numColSIMD};
    static constexpr int numAccumulators{MicroKernel::numAccumulators};
    static constexpr int microCols{MicroKernel::microCols};

    using Accumulators = typename MicroKernel::Accumulators;
    using BRegisters = typename MicroKernel::BRegisters;

    static Vector<T> packA(T const *A,
                           int iBegin,
                           int iEnd,
                           int iCount,
                           int kBegin,
                           int kEnd,
                           int kCount,
                           int K)
    {
        int const rowPanelCount{(iCount + microRows - 1) / microRows};
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
                           int packedSize,
                           int N)
    {
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

    static void run(T const *packedA,
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
            loadB<0>(bPtr, b);
            updateRows<0>(aPtr, b, c);
        }

        storeC<0>(C, c, iBegin, jBegin, N);
    }

private:
    template <int numB>
    static inline void loadB(T const *bPtr, BRegisters &b)
    {
        if constexpr (numB < numColSIMD)
        {
            b[numB] = Simd::load(bPtr + numB * Simd::lanes);

            loadB<numB + 1>(bPtr, b);
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
    static inline void updateRows(T const *aPtr,
                                  BRegisters const &b,
                                  Accumulators &c) noexcept
    {
        if constexpr (rowC < microRows)
        {
            Vec a{Simd::set1(aPtr[rowC])};

            updateCols<rowC, 0>(a, b, c);

            updateRows<rowC + 1>(aPtr, b, c);
        }
    }
};
