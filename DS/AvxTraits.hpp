#pragma once

#include <type_traits>
#include <immintrin.h>

template <typename T>
struct AvxTraits
{
    using Vec = std::conditional_t<
        std::is_same_v<T, float>,
        __m256,
        __m256d>;

    static constexpr int lanes{std::is_same_v<T, float> ? 8 : 4};

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

    static void avxSIMD(T const &a,
                        T const *BRow,
                        T *CRow,
                        int jBegin,
                        int jEnd)
    {
        Vec va{set1(a)};

        int j{jBegin};

        for (; j + lanes <= jEnd; j += lanes)
        {
            Vec vb{load(BRow + j)};
            Vec vc{load(CRow + j)};

            vc = fmadd(va, vb, vc);

            store(CRow + j, vc);
        }

        for (; j < jEnd; ++j)
        {
            CRow[j] += a * BRow[j];
        }
    }
};
