/*
    Sorting Algorithm Performance Analyzer
    Algorithms: Selection Sort and Insertion Sort
    Language: C
*/

#include <stdio.h>
#include <stdlib.h>
#include <time.h>

#define MAX_SIZE 10000

typedef struct {
    long long comparisons;
    long long operations;  /* swaps for selection sort; shifts for insertion sort */
    double elapsedMs;
} SortStats;

int master[MAX_SIZE];
int selectionData[MAX_SIZE];
int insertionData[MAX_SIZE];
int selectionResult[MAX_SIZE];
int insertionResult[MAX_SIZE];

int n = 0;
int dataReady = 0;

void copyArray(const int source[], int destination[], int size) {
    for (int i = 0; i < size; i++) {
        destination[i] = source[i];
    }
}

void displayArray(const int a[], int size) {
    if (size == 0) {
        printf("Dataset is empty.\n");
        return;
    }

    for (int i = 0; i < size; i++) {
        printf("%d ", a[i]);
        if ((i + 1) % 20 == 0) {
            printf("\n");
        }
    }
    printf("\n");
}

int isSorted(const int a[], int size) {
    for (int i = 1; i < size; i++) {
        if (a[i - 1] > a[i]) {
            return 0;
        }
    }
    return 1;
}

int arraysEqual(const int a[], const int b[], int size) {
    for (int i = 0; i < size; i++) {
        if (a[i] != b[i]) {
            return 0;
        }
    }
    return 1;
}

void selectionSort(int a[], int size, SortStats *stats) {
    stats->comparisons = 0;
    stats->operations = 0;

    clock_t start = clock();

    for (int i = 0; i < size - 1; i++) {
        int minIndex = i;

        for (int j = i + 1; j < size; j++) {
            stats->comparisons++;
            if (a[j] < a[minIndex]) {
                minIndex = j;
            }
        }

        if (minIndex != i) {
            int temp = a[i];
            a[i] = a[minIndex];
            a[minIndex] = temp;
            stats->operations++; /* one actual swap */
        }
    }

    clock_t end = clock();
    stats->elapsedMs = 1000.0 * (double)(end - start) / CLOCKS_PER_SEC;
}

void insertionSort(int a[], int size, SortStats *stats) {
    stats->comparisons = 0;
    stats->operations = 0;

    clock_t start = clock();

    for (int i = 1; i < size; i++) {
        int key = a[i];
        int j = i - 1;

        while (j >= 0) {
            stats->comparisons++;
            if (a[j] > key) {
                a[j + 1] = a[j];
                stats->operations++; /* one shift */
                j--;
            } else {
                break;
            }
        }

        a[j + 1] = key;
    }

    clock_t end = clock();
    stats->elapsedMs = 1000.0 * (double)(end - start) / CLOCKS_PER_SEC;
}

int readSize(void) {
    int size;
    printf("Enter dataset size (1-%d): ", MAX_SIZE);

    if (scanf("%d", &size) != 1) {
        printf("Invalid input.\n");
        exit(1);
    }

    if (size < 1 || size > MAX_SIZE) {
        printf("Size must be between 1 and %d.\n", MAX_SIZE);
        return -1;
    }

    return size;
}

void enterData(void) {
    int size = readSize();
    if (size == -1) return;

    printf("Enter %d integer values:\n", size);
    for (int i = 0; i < size; i++) {
        if (scanf("%d", &master[i]) != 1) {
            printf("Invalid value. Dataset was not updated.\n");
            return;
        }
    }

    n = size;
    dataReady = 1;
    printf("Dataset saved as the untouched master copy.\n");
}

void generateData(void) {
    int size;
    int choice;

    size = readSize();
    if (size == -1) return;

    printf("\nChoose arrangement:\n");
    printf("1. Sorted order (ascending)\n");
    printf("2. Reverse-sorted order (descending)\n");
    printf("3. Random order\n");
    printf("Enter choice: ");

    if (scanf("%d", &choice) != 1) {
        printf("Invalid input.\n");
        exit(1);
    }

    if (choice < 1 || choice > 3) {
        printf("Invalid arrangement choice.\n");
        return;
    }

    if (choice == 1) {
        for (int i = 0; i < size; i++) master[i] = i + 1;
    } else if (choice == 2) {
        for (int i = 0; i < size; i++) master[i] = size - i;
    } else {
        srand((unsigned int)time(NULL));
        for (int i = 0; i < size; i++) {
            master[i] = rand() % 100000;
        }
    }

    n = size;
    dataReady = 1;
    printf("Dataset generated successfully.\n");
}

void runSelection(void) {
    SortStats stats;

    if (!dataReady) {
        printf("Please enter or generate a dataset first.\n");
        return;
    }

    copyArray(master, selectionData, n);
    selectionSort(selectionData, n, &stats);
    copyArray(selectionData, selectionResult, n);

    printf("\nSelection Sort result:\n");
    displayArray(selectionResult, n);
    printf("Comparisons: %lld\n", stats.comparisons);
    printf("Swaps:      %lld\n", stats.operations);
    printf("Time:       %.3f ms\n", stats.elapsedMs);
    printf("Sorted correctly: %s\n", isSorted(selectionResult, n) ? "YES" : "NO");
}

void runInsertion(void) {
    SortStats stats;

    if (!dataReady) {
        printf("Please enter or generate a dataset first.\n");
        return;
    }

    copyArray(master, insertionData, n);
    insertionSort(insertionData, n, &stats);
    copyArray(insertionData, insertionResult, n);

    printf("\nInsertion Sort result:\n");
    displayArray(insertionResult, n);
    printf("Comparisons: %lld\n", stats.comparisons);
    printf("Shifts:      %lld\n", stats.operations);
    printf("Time:        %.3f ms\n", stats.elapsedMs);
    printf("Sorted correctly: %s\n", isSorted(insertionResult, n) ? "YES" : "NO");
}

void compareBoth(void) {
    SortStats selectionStats, insertionStats;
    double selectionTotalMs = 0.0, insertionTotalMs = 0.0;
    int trials;

    if (!dataReady) {
        printf("Please enter or generate a dataset first.\n");
        return;
    }

    printf("Enter number of timing trials (1-100): ");
    if (scanf("%d", &trials) != 1) {
        printf("Invalid input.\n");
        exit(1);
    }
    if (trials < 1 || trials > 100) {
        printf("Number of trials must be between 1 and 100.\n");
        return;
    }

    /*
       Each trial starts from the same untouched master array.
       Counters are deterministic for a given input; elapsed time is averaged.
    */
    for (int t = 0; t < trials; t++) {
        copyArray(master, selectionData, n);
        copyArray(master, insertionData, n);

        selectionSort(selectionData, n, &selectionStats);
        insertionSort(insertionData, n, &insertionStats);

        selectionTotalMs += selectionStats.elapsedMs;
        insertionTotalMs += insertionStats.elapsedMs;
    }

    /* Keep the final trial's sorted outputs for correctness verification. */
    copyArray(selectionData, selectionResult, n);
    copyArray(insertionData, insertionResult, n);

    printf("\n========== PERFORMANCE COMPARISON ==========\n");
    printf("Dataset size: %d | Timing trials: %d\n", n, trials);
    printf("Original dataset:\n");
    displayArray(master, n);

    printf("\n%-18s | %-12s | %-12s | %-15s\n",
           "Algorithm", "Comparisons", "Swaps/Shifts", "Average time (ms)");
    printf("-------------------+--------------+--------------+-----------------\n");
    printf("%-18s | %-12lld | %-12lld | %-15.3f\n",
           "Selection Sort", selectionStats.comparisons,
           selectionStats.operations, selectionTotalMs / trials);
    printf("%-18s | %-12lld | %-12lld | %-15.3f\n",
           "Insertion Sort", insertionStats.comparisons,
           insertionStats.operations, insertionTotalMs / trials);

    printf("\nSelection Sort output:\n");
    displayArray(selectionResult, n);
    printf("Insertion Sort output:\n");
    displayArray(insertionResult, n);

    printf("Selection output is sorted: %s\n",
           isSorted(selectionResult, n) ? "YES" : "NO");
    printf("Insertion output is sorted: %s\n",
           isSorted(insertionResult, n) ? "YES" : "NO");
    printf("Both outputs are identical: %s\n",
           arraysEqual(selectionResult, insertionResult, n) ? "YES" : "NO");

    printf("\nInterpretation:\n");
    printf("- Selection Sort performs n(n-1)/2 comparisons for every arrangement.\n");
    printf("- Insertion Sort usually performs fewer comparisons on already sorted data.\n");
    printf("- Timing is averaged across the requested trials; very small runs may show 0.000 ms.\n");
    printf("- Repeat with different sizes and arrangements to compare practical behaviour.\n");
}

void showMenu(void) {
    printf("\n");
    printf("=============================================\n");
    printf("   SORTING ALGORITHM PERFORMANCE ANALYZER\n");
    printf("=============================================\n");
    printf("1. Enter dataset manually\n");
    printf("2. Generate dataset\n");
    printf("3. Display original dataset\n");
    printf("4. Run Selection Sort\n");
    printf("5. Run Insertion Sort\n");
    printf("6. Compare both algorithms\n");
    printf("7. Exit\n");
    printf("---------------------------------------------\n");
    printf("Enter your choice: ");
}

int main(void) {
    int choice;

    while (1) {
        showMenu();

        if (scanf("%d", &choice) != 1) {
            printf("Invalid input. Please enter a menu number.\n");
            break;
        }

        switch (choice) {
            case 1:
                enterData();
                break;
            case 2:
                generateData();
                break;
            case 3:
                if (dataReady) {
                    printf("\nOriginal master dataset:\n");
                    displayArray(master, n);
                } else {
                    printf("No dataset available. Enter or generate data first.\n");
                }
                break;
            case 4:
                runSelection();
                break;
            case 5:
                runInsertion();
                break;
            case 6:
                compareBoth();
                break;
            case 7:
                printf("Thank you for using the analyzer!\n");
                return 0;
            default:
                printf("Invalid choice. Please select 1-7.\n");
        }
    }

    return 0;
}
