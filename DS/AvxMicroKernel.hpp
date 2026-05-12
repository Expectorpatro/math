#pragma once

#include "AvxTraits.hpp"

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

private:
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
};
